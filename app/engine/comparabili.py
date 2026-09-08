"""Stima del valore di mercato al mq per zona, tipologia e finestra temporale.

Architettura a provider: la baseline interna e' sostituibile con quotazioni
ufficiali OMI o con un CSV di comparabili caricato dall'utente, senza toccare
il resto del motore.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from app import config
from app.models import Immobile

FINESTRE = {"m3": 0.125, "m6": 0.25, "m12": 0.5}  # anni indietro del punto medio finestra
ETICHETTE_FINESTRE = {"m3": "Ultimi 3 mesi", "m6": "Ultimi 6 mesi", "m12": "Ultimi 12 mesi"}


@dataclass
class Comparabile:
    eur_mq: float = 0.0
    eur_mq_min: float = 0.0
    eur_mq_max: float = 0.0
    serie: dict[str, float] = field(default_factory=dict)
    variazione_annua: float = 0.0
    fonte: str = ""
    affidabilita: str = "bassa"
    zona: str = ""
    note: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "eur_mq": round(self.eur_mq, 2),
            "eur_mq_min": round(self.eur_mq_min, 2),
            "eur_mq_max": round(self.eur_mq_max, 2),
            "serie": {k: round(v, 2) for k, v in self.serie.items()},
            "etichette": ETICHETTE_FINESTRE,
            "variazione_annua": round(self.variazione_annua, 4),
            "fonte": self.fonte,
            "affidabilita": self.affidabilita,
            "zona": self.zona,
            "note": self.note,
        }


# --------------------------------------------------------------------------
# Provider 1: comparabili forniti dall'utente (CSV) - massima priorita'
# --------------------------------------------------------------------------

PERCORSO_CSV_UTENTE = config.DATA_DIR / "comparabili_utente.csv"
INTESTAZIONI_CSV = [
    "provincia", "comune", "tipologia", "eur_mq", "eur_mq_min", "eur_mq_max",
    "variazione_annua", "fonte", "data",
]


def _carica_csv_utente() -> list[dict]:
    if not PERCORSO_CSV_UTENTE.exists():
        return []
    with open(PERCORSO_CSV_UTENTE, encoding="utf-8-sig", newline="") as fh:
        return [
            {(k or "").strip().lower(): (v or "").strip() for k, v in riga.items()}
            for riga in csv.DictReader(fh)
        ]


def _da_csv_utente(imm: Immobile) -> Comparabile | None:
    righe = _carica_csv_utente()
    if not righe:
        return None
    comune = (imm.comune or "").strip().lower()
    provincia = (imm.provincia or "").strip().upper()

    def compatibile(r: dict, per_comune: bool) -> bool:
        if r.get("tipologia") and r["tipologia"].lower() not in (imm.tipologia, "*", "tutte"):
            return False
        if per_comune:
            return bool(comune) and r.get("comune", "").lower() == comune
        return bool(provincia) and r.get("provincia", "").upper() == provincia

    for per_comune in (True, False):
        candidate = [r for r in righe if compatibile(r, per_comune)]
        if not candidate:
            continue
        r = candidate[0]
        try:
            base = float(str(r["eur_mq"]).replace(",", "."))
        except (KeyError, ValueError):
            continue
        try:
            trend = float(str(r.get("variazione_annua") or 0).replace(",", "."))
        except ValueError:
            trend = 0.0
        return Comparabile(
            eur_mq=base,
            eur_mq_min=float(r.get("eur_mq_min") or base * 0.8),
            eur_mq_max=float(r.get("eur_mq_max") or base * 1.25),
            serie=_serie(base, trend),
            variazione_annua=trend,
            fonte=r.get("fonte") or "Comparabili caricati dall'utente (CSV)",
            affidabilita="alta",
            zona=r.get("comune") or r.get("provincia") or "",
        )
    return None


# --------------------------------------------------------------------------
# Provider 2: baseline interna per provincia
# --------------------------------------------------------------------------

def _serie(base: float, trend: float) -> dict[str, float]:
    """Ricostruisce il prezzo medio delle transazioni per finestra temporale.

    Il valore ``base`` e' il livello corrente; ogni finestra viene riportata
    indietro al proprio punto medio con il trend annuo della zona.
    """
    return {k: base / ((1.0 + trend) ** anni) for k, anni in FINESTRE.items()}


def _valore_terreno(imm: Immobile, mkt: dict, residenziale: float) -> tuple[float, str, list[str]]:
    """Valore al mq di TERRENO.

    Un terreno edificabile non vale i suoi mq al prezzo del costruito: vale l'area
    edificabile che esprime. Si applica quindi l'incidenza dell'area sul valore del
    costruito, moltiplicata per l'indice di edificabilita' (mq costruibili per mq di
    terreno). Se il file non riporta l'indice si usa quello di default, che e'
    l'ipotesi piu' pesante di tutto il calcolo: va verificata sul PRG del Comune.
    """
    t = mkt["terreni"]
    destinazione = imm.destinazione_terreno
    note: list[str] = []

    if destinazione in {"edificabile", "industriale"}:
        industriale = destinazione == "industriale"
        indice_default = float(
            t["indice_edificabilita_industriale_mq_mq"] if industriale
            else t["indice_edificabilita_default_mq_mq"]
        )
        incidenza = float(
            t["incidenza_area_industriale"] if industriale
            else t["incidenza_area_su_valore_costruito"]
        )
        indice = float(imm.indice_edificabilita or indice_default)
        if not imm.indice_edificabilita:
            note.append(
                f"Indice di edificabilita' non presente nel file: ipotizzato {indice_default} mq/mq. "
                "Verificare il PRG comunale: e' il parametro che pesa di piu' sul valore."
            )
        base_costruito = residenziale * (0.45 if industriale else 1.0)
        etichetta = f"terreno {'industriale' if industriale else 'edificabile'} (indice {indice:g} mq/mq)"
        return base_costruito * incidenza * indice, etichetta, note

    agricoli = mkt["terreno_agricolo_eur_mq_per_regione"]
    valore = float(agricoli.get(imm.regione, agricoli["_default"]))
    etichetta = "terreno agricolo" if destinazione == "agricolo" else "terreno (destinazione ignota)"
    return valore, etichetta, note


def _da_baseline(imm: Immobile) -> Comparabile:
    mkt = config.mercato()
    residenziali = mkt["residenziale_eur_mq"]
    trend_tab = mkt["trend_annuo_per_provincia"]
    note: list[str] = []

    provincia = imm.provincia if imm.provincia in residenziali else ""
    if provincia:
        residenziale = float(residenziali[provincia])
        affidabilita = "media"
        zona = f"{imm.comune or provincia} ({provincia})"
    else:
        residenziale = sum(residenziali.values()) / len(residenziali)
        affidabilita = "bassa"
        zona = "media nazionale"
        note.append("Provincia non riconosciuta: applicata la media nazionale.")

    if imm.e_terreno:
        base, etichetta, note_terreno = _valore_terreno(imm, mkt, residenziale)
        note.extend(note_terreno)
        if imm.destinazione_terreno == "sconosciuto":
            note.append("Destinazione urbanistica non indicata: ipotizzato uso agricolo (ipotesi prudenziale).")
    else:
        ratio = mkt["ratio_per_tipologia"].get(imm.tipologia, mkt["ratio_per_tipologia"]["altro"])
        base = residenziale * ratio
        etichetta = imm.tipologia

    trend = float(trend_tab.get(provincia, trend_tab["_default"])) if provincia else float(trend_tab["_default"])

    return Comparabile(
        eur_mq=base,
        eur_mq_min=base * 0.78,
        eur_mq_max=base * 1.28,
        serie=_serie(base, trend),
        variazione_annua=trend,
        fonte=f"{config.mercato()['_meta']['fonte']} - {etichetta}",
        affidabilita=affidabilita,
        zona=zona,
        note=note,
    )


# --------------------------------------------------------------------------
# Punto di ingresso
# --------------------------------------------------------------------------

def stima(imm: Immobile) -> Comparabile:
    """Comparabile piu' attendibile disponibile per questo immobile."""
    return _da_csv_utente(imm) or _da_baseline(imm)


def scrivi_modello_csv(percorso: Path | None = None) -> Path:
    """Crea il CSV di esempio per i comparabili propri dell'utente."""
    percorso = percorso or (config.DATA_DIR / "comparabili_utente.esempio.csv")
    with open(percorso, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(INTESTAZIONI_CSV)
        w.writerow(["MI", "Milano", "residenziale", "4600", "3200", "8000", "0.021",
                    "OMI 2026/1 + rilevazione interna", "2026-01"])
        w.writerow(["MI", "", "capannone", "780", "500", "1100", "0.010",
                    "Rilevazione interna", "2026-01"])
    return percorso
