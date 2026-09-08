#!/usr/bin/env python3
"""Sostituisce la baseline di mercato con le quotazioni ufficiali OMI.

L'Agenzia delle Entrate pubblica le quotazioni immobiliari OMI in file semestrali
(zip di CSV con separatore ';'). Sono la fonte piu' autorevole disponibile
gratuitamente per il valore al mq per zona.

    1. Scarica il file da:
       https://www1.agenziaentrate.gov.it/servizi/geopoi_omi/index.php
       (sezione "Quotazioni immobiliari - dati in formato elaborabile")
    2. Esegui:
       python scripts/importa_omi.py QI_<anno><semestre>_VALORI.zip

Lo script produce app/data/comparabili_utente.csv, che ha la precedenza sulla
baseline interna: da quel momento la dashboard usa i valori ufficiali.
"""
from __future__ import annotations

import csv
import io
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DESTINAZIONE = RADICE / "app" / "data" / "comparabili_utente.csv"

# Destinazione d'uso OMI -> tipologia del nostro schema
TIPOLOGIE_OMI = {
    "abitazioni civili": "residenziale",
    "abitazioni di tipo economico": "residenziale",
    "abitazioni signorili": "residenziale",
    "ville e villini": "residenziale",
    "uffici": "ufficio",
    "uffici strutturati": "ufficio",
    "negozi": "commerciale",
    "magazzini": "capannone",
    "capannoni industriali": "capannone",
    "capannoni tipici": "capannone",
    "laboratori": "capannone",
    "box": "box",
    "autorimesse": "box",
    "posti auto coperti": "box",
}


def _numero(valore: str) -> float | None:
    testo = (valore or "").strip().replace(".", "").replace(",", ".")
    try:
        n = float(testo)
    except ValueError:
        return None
    return n if n > 0 else None


def _righe_csv(percorso: Path):
    """Restituisce le righe dei CSV dei valori, sia da zip che da file singolo."""
    if percorso.suffix.lower() == ".zip":
        with zipfile.ZipFile(percorso) as archivio:
            for nome in archivio.namelist():
                if not nome.lower().endswith(".csv") or "zone" in nome.lower():
                    continue
                with archivio.open(nome) as fh:
                    yield from _analizza(io.TextIOWrapper(fh, encoding="latin-1"))
    else:
        with open(percorso, encoding="latin-1") as fh:
            yield from _analizza(fh)


def _analizza(flusso):
    """I file OMI hanno una riga di preambolo prima dell'intestazione vera."""
    righe = flusso.read().splitlines()
    inizio = next(
        (i for i, r in enumerate(righe) if "Compr_min" in r or "Comp_min" in r), 0
    )
    yield from csv.DictReader(righe[inizio:], delimiter=";")


def importa(percorso: Path) -> int:
    aggregato: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)

    for riga in _righe_csv(percorso):
        normalizzata = {(k or "").strip().lower(): (v or "").strip() for k, v in riga.items()}
        provincia = (normalizzata.get("prov") or "").upper()[:2]
        descrizione = (normalizzata.get("descr_tipologia") or "").lower()
        tipologia = TIPOLOGIE_OMI.get(descrizione)
        minimo = _numero(normalizzata.get("compr_min") or normalizzata.get("comp_min") or "")
        massimo = _numero(normalizzata.get("compr_max") or normalizzata.get("comp_max") or "")
        if not (provincia and tipologia and minimo and massimo):
            continue
        aggregato[(provincia, tipologia)].append((minimo, massimo))

    if not aggregato:
        print("Nessuna quotazione riconosciuta: il file non sembra un export OMI dei valori.",
              file=sys.stderr)
        return 0

    DESTINAZIONE.parent.mkdir(parents=True, exist_ok=True)
    with open(DESTINAZIONE, "w", encoding="utf-8", newline="") as fh:
        scrittore = csv.writer(fh)
        scrittore.writerow(["provincia", "comune", "tipologia", "eur_mq", "eur_mq_min",
                            "eur_mq_max", "variazione_annua", "fonte", "data"])
        for (provincia, tipologia), valori in sorted(aggregato.items()):
            minimi = [v[0] for v in valori]
            massimi = [v[1] for v in valori]
            medio = (sum(minimi) + sum(massimi)) / (2 * len(valori))
            scrittore.writerow([
                provincia, "", tipologia, f"{medio:.0f}",
                f"{min(minimi):.0f}", f"{max(massimi):.0f}", "0",
                f"OMI Agenzia delle Entrate - {percorso.name}", "",
            ])
    return len(aggregato)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    percorso = Path(sys.argv[1])
    if not percorso.exists():
        print(f"File non trovato: {percorso}", file=sys.stderr)
        return 1
    quante = importa(percorso)
    if not quante:
        return 1
    print(f"Importate {quante} combinazioni provincia/tipologia in {DESTINAZIONE}")
    print("La dashboard usera' d'ora in poi le quotazioni OMI al posto della baseline interna.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
