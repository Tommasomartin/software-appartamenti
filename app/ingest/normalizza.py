"""Conversione delle righe grezze nello schema canonico ``Immobile``."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from app.ingest import excel as lettore_excel
from app.ingest import pdf as lettore_pdf
from app.ingest.mapping import (
    CAMPI_TESTUALI_PER_FAB,
    classifica_conservazione,
    classifica_destinazione_terreno,
    classifica_occupazione,
    classifica_tipologia,
    estrai_fab,
    numero,
    rileva_colonne,
    risolvi_geografia,
    slug,
)
from app.models import Immobile

ESTENSIONI_SUPPORTATE = {".xlsx", ".xlsm", ".xls", ".xltx", ".csv", ".tsv", ".txt", ".pdf"}


def _testo(valore: object) -> str:
    if valore is None:
        return ""
    s = str(valore).strip()
    return "" if s.lower() in {"nan", "none", "nat", "n.d.", "n/a", "-"} else s


def _riga_vuota(riga: dict) -> bool:
    return not any(_testo(v) for v in riga.values())


def _identificativo(portafoglio_id: int, foglio: str, indice: int, riga: dict) -> str:
    impronta = hashlib.sha1(
        f"{portafoglio_id}|{foglio}|{indice}|{sorted(map(str, riga.values()))}".encode()
    ).hexdigest()[:10]
    return f"{portafoglio_id}-{impronta}"


def _valore(riga: dict, mappa: dict[str, str], campo: str) -> object:
    colonna = mappa.get(campo)
    return riga.get(colonna) if colonna else None


def normalizza_dataframe(
    df: pd.DataFrame, portafoglio_id: int, foglio: str
) -> tuple[list[Immobile], dict]:
    intestazioni = [str(c) for c in df.columns]
    mappa = rileva_colonne(intestazioni)
    immobili: list[Immobile] = []
    scartate = 0

    for indice, riga_serie in enumerate(df.to_dict(orient="records")):
        riga = {str(k): v for k, v in riga_serie.items()}
        if _riga_vuota(riga):
            continue

        imm = Immobile(portafoglio_id=portafoglio_id)
        imm.raw = {k: _testo(v) for k, v in riga.items() if _testo(v)}
        imm.id = _identificativo(portafoglio_id, foglio, indice, imm.raw)

        imm.lotto = _testo(_valore(riga, mappa, "lotto")) or f"riga {indice + 1}"
        imm.note = _testo(_valore(riga, mappa, "note"))
        imm.indirizzo = _testo(_valore(riga, mappa, "indirizzo"))
        imm.cap = _testo(_valore(riga, mappa, "cap"))
        imm.piano = _testo(_valore(riga, mappa, "piano"))
        imm.categoria_catastale = _testo(_valore(riga, mappa, "categoria_catastale")).upper()
        imm.foglio = _testo(_valore(riga, mappa, "foglio"))
        imm.particella = _testo(_valore(riga, mappa, "particella"))
        imm.subalterno = _testo(_valore(riga, mappa, "subalterno"))

        # FAB: colonna dedicata, altrimenti ricerca nei campi testuali, altrimenti in tutta la riga
        candidati = [_valore(riga, mappa, "fab_raw")]
        candidati += [getattr(imm, c, "") for c in CAMPI_TESTUALI_PER_FAB if hasattr(imm, c)]
        imm.fab, imm.fab_raw = estrai_fab(*candidati)
        if imm.fab is None:
            imm.fab, imm.fab_raw = estrai_fab(*riga.values())

        imm.tipologia = classifica_tipologia(
            _valore(riga, mappa, "tipologia"), imm.categoria_catastale, imm.note, imm.lotto
        )
        imm.stato_occupazione = classifica_occupazione(
            _valore(riga, mappa, "stato_occupazione"), imm.note
        )
        imm.stato_conservazione = classifica_conservazione(
            _valore(riga, mappa, "stato_conservazione"), imm.note
        )
        imm.destinazione_terreno = classifica_destinazione_terreno(
            _valore(riga, mappa, "destinazione_terreno"),
            _valore(riga, mappa, "tipologia"),
            imm.note,
        )

        imm.comune, imm.provincia, imm.regione = risolvi_geografia(
            _testo(_valore(riga, mappa, "comune")),
            _testo(_valore(riga, mappa, "provincia")),
            _testo(_valore(riga, mappa, "regione")),
        )

        imm.superficie_mq = numero(_valore(riga, mappa, "superficie_mq"))
        imm.vani = numero(_valore(riga, mappa, "vani"))
        imm.rendita_catastale = numero(_valore(riga, mappa, "rendita_catastale"))
        imm.canone_annuo = numero(_valore(riga, mappa, "canone_annuo"))
        imm.indice_edificabilita = numero(_valore(riga, mappa, "indice_edificabilita"))
        imm.lat = numero(_valore(riga, mappa, "lat"))
        imm.lng = numero(_valore(riga, mappa, "lng"))
        imm.prezzo_base = numero(_valore(riga, mappa, "prezzo_base"))
        imm.prezzo_perizia = numero(_valore(riga, mappa, "prezzo_perizia"))

        if imm.prezzo_base is None and imm.prezzo_perizia is not None:
            imm.prezzo_base = imm.prezzo_perizia
            imm.warning_ingest.append("Prezzo base assente: usato il valore di perizia.")

        if imm.prezzo_base is None:
            scartate += 1
            imm.warning_ingest.append("Nessun prezzo rilevato nel file.")
        if not imm.superficie_mq and not imm.e_terreno:
            imm.warning_ingest.append("Superficie assente: stime a mq non calcolabili.")
        if not imm.provincia:
            imm.warning_ingest.append("Provincia non riconosciuta: uso parametri nazionali medi.")
        if imm.fab is None:
            imm.warning_ingest.append("FAB non trovato: applicata la percentuale di default.")

        immobili.append(imm)

    diagnostica = {
        "foglio": foglio,
        "righe_lette": len(immobili),
        "righe_senza_prezzo": scartate,
        "colonne_riconosciute": mappa,
        "colonne_ignorate": [c for c in intestazioni if c not in set(mappa.values())],
    }
    return immobili, diagnostica


def carica_file(percorso: Path, portafoglio_id: int) -> tuple[list[Immobile], list[dict]]:
    suffisso = percorso.suffix.lower()
    if suffisso not in ESTENSIONI_SUPPORTATE:
        raise ValueError(
            f"Formato '{suffisso}' non supportato. Ammessi: "
            + ", ".join(sorted(ESTENSIONI_SUPPORTATE))
        )

    fogli = lettore_pdf.leggi(percorso) if suffisso == ".pdf" else lettore_excel.leggi(percorso)
    if not fogli:
        raise ValueError("Nessuna tabella leggibile trovata nel file.")

    tutti: list[Immobile] = []
    diagnostiche: list[dict] = []
    for nome, df in fogli:
        immobili, diagnostica = normalizza_dataframe(df, portafoglio_id, nome)
        # Salta i fogli di servizio (legende, note) privi di dati utili
        utili = sum(1 for i in immobili if i.prezzo_base or i.superficie_mq)
        diagnostica["utilizzato"] = bool(utili)
        diagnostiche.append(diagnostica)
        if utili:
            tutti.extend(immobili)

    if not tutti:
        raise ValueError(
            "Nessun immobile riconosciuto: nel file non sono state trovate colonne "
            "di prezzo o superficie."
        )
    return tutti, diagnostiche
