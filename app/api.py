"""API HTTP della dashboard."""
from __future__ import annotations

import io
import shutil
from typing import Any

import pandas as pd
from fastapi import APIRouter, Body, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app import config, storage
from app.engine import comparabili, geo, punteggio, valutazione
from app.ingest.normalizza import ESTENSIONI_SUPPORTATE, carica_file
from app.models import Immobile

router = APIRouter(prefix="/api")

# Campi che l'utente puo' correggere a mano dalla scheda immobile
CAMPI_MODIFICABILI = {
    "fab": int, "tipologia": str, "superficie_mq": float, "prezzo_base": float,
    "prezzo_perizia": float, "stato_occupazione": str, "stato_conservazione": str,
    "destinazione_terreno": str, "indice_edificabilita": float, "canone_annuo": float,
    "rendita_catastale": float, "categoria_catastale": str, "comune": str,
    "provincia": str, "indirizzo": str, "cap": str, "piano": str,
    "lat": float, "lng": float, "note": str,
}


# --------------------------------------------------------------------------
# Caricamento file
# --------------------------------------------------------------------------

@router.post("/carica")
async def carica(file: UploadFile) -> dict:
    nome = file.filename or "senza-nome"
    estensione = "." + nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    if estensione not in ESTENSIONI_SUPPORTATE:
        raise HTTPException(
            400,
            f"Formato '{estensione or 'sconosciuto'}' non supportato. "
            f"Ammessi: {', '.join(sorted(ESTENSIONI_SUPPORTATE))}",
        )

    portafoglio_id = storage.crea_portafoglio(nome.rsplit(".", 1)[0], nome)
    destinazione = config.UPLOAD_DIR / f"{portafoglio_id}{estensione}"
    try:
        with open(destinazione, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        immobili, diagnostica = carica_file(destinazione, portafoglio_id)
    except Exception as exc:
        storage.elimina_portafoglio(portafoglio_id)
        destinazione.unlink(missing_ok=True)
        raise HTTPException(400, f"Non sono riuscito a leggere il file: {exc}") from exc

    storage.salva_immobili(immobili)
    storage.aggiorna_portafoglio(portafoglio_id, diagnostica, len(immobili))
    return {
        "portafoglio_id": portafoglio_id,
        "nome": nome,
        "immobili_importati": len(immobili),
        "diagnostica": diagnostica,
    }


@router.get("/portafogli")
def portafogli() -> list[dict]:
    return storage.elenca_portafogli()


@router.delete("/portafogli/{portafoglio_id}")
def elimina(portafoglio_id: int) -> dict:
    storage.elimina_portafoglio(portafoglio_id)
    return {"eliminato": portafoglio_id}


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

def _riga(imm: Immobile, ipotesi: dict, orizzonte: int) -> dict:
    p = valutazione.calcola(imm, ipotesi, orizzonte)
    return {"immobile": imm.to_dict(), "prospetto": p.to_dict(), "link": geo.link(imm)}


def _calcola_tutto(portafoglio_id: int | None, orizzonte: int) -> tuple[list[dict], dict, dict]:
    ipotesi = storage.leggi_ipotesi()
    orizzonte = orizzonte or int(ipotesi.get("orizzonte_mesi", 12))
    immobili = storage.carica_immobili(portafoglio_id)
    righe = [_riga(i, ipotesi, orizzonte) for i in immobili]
    righe.sort(key=lambda r: r["prospetto"]["punteggio"], reverse=True)
    return righe, ipotesi, {"orizzonte_mesi": orizzonte}


@router.get("/dashboard")
def dashboard(
    portafoglio_id: int | None = Query(None),
    orizzonte_mesi: int = Query(0, ge=0, le=120),
) -> dict:
    righe, ipotesi, meta = _calcola_tutto(portafoglio_id, orizzonte_mesi)
    prospetti = [valutazione.Prospetto(**r["prospetto"]) for r in righe]
    sintesi = punteggio.riepilogo(prospetti)
    sintesi["prezzo_base_totale"] = sum(
        float(r["immobile"]["prezzo_base"] or 0) for r in righe
    )
    return {
        "righe": righe,
        "riepilogo": sintesi,
        "ipotesi": ipotesi,
        "meta": {**meta, "portafogli": storage.elenca_portafogli()},
    }


@router.get("/immobile/{immobile_id}")
def dettaglio(immobile_id: str, orizzonte_mesi: int = Query(0, ge=0, le=120)) -> dict:
    imm = storage.carica_immobile(immobile_id)
    if imm is None:
        raise HTTPException(404, "Immobile non trovato.")
    ipotesi = storage.leggi_ipotesi()
    orizzonte = orizzonte_mesi or int(ipotesi.get("orizzonte_mesi", 12))
    return _riga(imm, ipotesi, orizzonte)


@router.patch("/immobile/{immobile_id}")
def correggi(immobile_id: str, modifiche: dict[str, Any] = Body(...)) -> dict:
    """Correzione manuale di un campo letto male dal file."""
    imm = storage.carica_immobile(immobile_id)
    if imm is None:
        raise HTTPException(404, "Immobile non trovato.")

    for campo, valore in modifiche.items():
        if campo not in CAMPI_MODIFICABILI:
            continue
        tipo = CAMPI_MODIFICABILI[campo]
        if valore in (None, ""):
            setattr(imm, campo, None if tipo is not str else "")
            continue
        try:
            convertito = tipo(float(valore)) if tipo in (int, float) else str(valore).strip()
        except (TypeError, ValueError):
            raise HTTPException(400, f"Valore non valido per '{campo}': {valore!r}")
        setattr(imm, campo, convertito)

    if any(c in modifiche for c in ("comune", "provincia")):
        from app.ingest.mapping import risolvi_geografia
        imm.comune, imm.provincia, imm.regione = risolvi_geografia(
            imm.comune, imm.provincia, imm.regione
        )
    imm.warning_ingest = [w for w in imm.warning_ingest if "non trovat" not in w.lower()]
    imm.warning_ingest.append("Dati corretti manualmente.")
    storage.aggiorna_immobile(imm)

    ipotesi = storage.leggi_ipotesi()
    return _riga(imm, ipotesi, int(ipotesi.get("orizzonte_mesi", 12)))


# --------------------------------------------------------------------------
# Ipotesi
# --------------------------------------------------------------------------

@router.get("/ipotesi")
def leggi_ipotesi() -> dict:
    return storage.leggi_ipotesi()


@router.put("/ipotesi")
def salva_ipotesi(ipotesi: dict[str, Any] = Body(...)) -> dict:
    return storage.salva_ipotesi(ipotesi)


@router.post("/ipotesi/reset")
def reset_ipotesi() -> dict:
    return storage.azzera_ipotesi()


# --------------------------------------------------------------------------
# Comparabili di mercato
# --------------------------------------------------------------------------

@router.get("/comparabili/modello.csv")
def modello_comparabili() -> StreamingResponse:
    percorso = comparabili.scrivi_modello_csv()
    return StreamingResponse(
        io.BytesIO(percorso.read_bytes()),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="comparabili_modello.csv"'},
    )


@router.post("/comparabili")
async def carica_comparabili(file: UploadFile) -> dict:
    contenuto = await file.read()
    testo = contenuto.decode("utf-8-sig", errors="replace")
    if "eur_mq" not in testo.split("\n", 1)[0].lower():
        raise HTTPException(400, "Il CSV deve contenere almeno le colonne 'provincia' e 'eur_mq'.")
    comparabili.PERCORSO_CSV_UTENTE.write_text(testo, encoding="utf-8")
    righe = max(0, len(testo.strip().splitlines()) - 1)
    return {"righe_caricate": righe, "attivo": True}


@router.delete("/comparabili")
def rimuovi_comparabili() -> dict:
    comparabili.PERCORSO_CSV_UTENTE.unlink(missing_ok=True)
    return {"attivo": False}


@router.get("/comparabili/stato")
def stato_comparabili() -> dict:
    attivo = comparabili.PERCORSO_CSV_UTENTE.exists()
    return {
        "attivo": attivo,
        "fonte_baseline": config.mercato()["_meta"]["fonte"],
        "aggiornamento": config.mercato()["_meta"]["aggiornamento"],
    }


# --------------------------------------------------------------------------
# Esportazione
# --------------------------------------------------------------------------

COLONNE_EXPORT = [
    ("lotto", "Lotto"), ("fab", "FAB"), ("tipologia", "Tipologia"),
    ("comune", "Comune"), ("provincia", "Prov"), ("indirizzo", "Indirizzo"),
    ("superficie_mq", "Superficie mq"), ("stato_occupazione", "Occupazione"),
    ("stato_conservazione", "Conservazione"), ("prezzo_base", "Prezzo da file"),
]

COLONNE_PROSPETTO = [
    ("percentuale_acquisto", "% acquisto"), ("prezzo_acquisto", "Prezzo acquisto"),
    ("imposta_registro", "Imposta registro 2%"), ("notaio", "Notaio"),
    ("commissione_acquisto", "Agenzia acquisto"), ("altri_costi_acquisto", "Altri costi"),
    ("capex_ristrutturazione", "Ristrutturazione"), ("cassa_iniziale", "Cassa iniziale"),
    ("imu_annua", "IMU annua"), ("oneri_annui", "Oneri annui"),
    ("ricavo_locazione_annuo", "Ricavo locazione annuo"),
    ("mantenimento_netto_annuo", "Mantenimento netto annuo"),
    ("valore_mercato_eur_mq", "Valore mercato EUR/mq"), ("prezzo_uscita", "Prezzo uscita"),
    ("commissione_vendita", "Agenzia vendita 2%"), ("incasso_netto", "Incasso netto"),
    ("investimento_totale", "Investimento totale"), ("utile", "Utile"),
    ("multiplo", "Multiplo"), ("roi", "ROI"), ("roi_annualizzato", "ROI annualizzato"),
    ("prezzo_pareggio", "Prezzo di pareggio"), ("confidenza", "Confidenza"),
    ("punteggio", "Punteggio"), ("semaforo", "Semaforo"),
]


@router.get("/esporta.xlsx")
def esporta(
    portafoglio_id: int | None = Query(None),
    orizzonte_mesi: int = Query(0, ge=0, le=120),
) -> StreamingResponse:
    righe, ipotesi, meta = _calcola_tutto(portafoglio_id, orizzonte_mesi)
    if not righe:
        raise HTTPException(404, "Nessun immobile da esportare.")

    record = []
    for r in righe:
        imm, pro = r["immobile"], r["prospetto"]
        voce: dict[str, Any] = {etichetta: imm.get(campo) for campo, etichetta in COLONNE_EXPORT}
        voce.update({etichetta: pro.get(campo) for campo, etichetta in COLONNE_PROSPETTO})
        serie = pro.get("comparabili", {}).get("serie", {})
        voce["EUR/mq ultimi 3 mesi"] = serie.get("m3")
        voce["EUR/mq ultimi 6 mesi"] = serie.get("m6")
        voce["EUR/mq ultimi 12 mesi"] = serie.get("m12")
        voce["Google Maps"] = r["link"]["google_maps"]
        voce["Google Earth"] = r["link"]["google_earth"]
        voce["Note calcolo"] = " | ".join(pro.get("motivazioni", []) + pro.get("warning", []))
        record.append(voce)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        pd.DataFrame(record).to_excel(writer, sheet_name="Prospetto", index=False)
        piatte = {
            f"{sezione}.{chiave}": valore
            for sezione, contenuto in ipotesi.items()
            if isinstance(contenuto, dict)
            for chiave, valore in contenuto.items()
            if not str(chiave).startswith("_")
        }
        pd.DataFrame(
            {"Parametro": list(piatte), "Valore": [str(v) for v in piatte.values()]}
        ).to_excel(writer, sheet_name="Ipotesi", index=False)
        foglio = writer.sheets["Prospetto"]
        foglio.freeze_panes(1, 1)
        foglio.autofilter(0, 0, len(record), len(record[0]) - 1 if record else 0)

    buffer.seek(0)
    nome = f"prospetto_{meta['orizzonte_mesi']}mesi.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.get("/riferimenti")
def riferimenti() -> dict:
    """Metadati delle fonti, mostrati nel pannello trasparenza."""
    return {
        "mercato": config.mercato()["_meta"],
        "imu": {k: v for k, v in config.imu_oneri()["_meta"].items()},
        "comparabili_utente_attivi": comparabili.PERCORSO_CSV_UTENTE.exists(),
    }
