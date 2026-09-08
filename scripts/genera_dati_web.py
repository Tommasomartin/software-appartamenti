#!/usr/bin/env python3
"""Rigenera il blocco dati incorporato nella pagina web a partire da app/data/.

Serve a tenere allineate la versione locale e quella a pagina singola: dopo aver
modificato un dataset in app/data/, eseguire questo script e ricontrollare la pagina.

    python scripts/genera_dati_web.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from app import config  # noqa: E402
from app.ingest.normalizza import carica_file  # noqa: E402

PAGINA = RADICE / "artifact" / "prospetto-lotti-fab.html"

CAMPI_ESEMPIO = (
    "lotto", "fab", "tipologia", "indirizzo", "comune", "provincia", "regione",
    "superficie_mq", "categoria_catastale", "rendita_catastale", "stato_occupazione",
    "stato_conservazione", "canone_annuo", "destinazione_terreno",
    "indice_edificabilita", "prezzo_base", "piano", "note",
)


def _senza_note(valore):
    """Rimuove le chiavi di commento (_nota, _meta) dai dataset."""
    if isinstance(valore, dict):
        return {k: _senza_note(v) for k, v in valore.items() if not str(k).startswith("_")}
    return valore


def costruisci() -> dict:
    mkt, imu = config.mercato(), config.imu_oneri()
    dati = {
        "province": config.geografia()["province"],
        "mercato": {
            "res": mkt["residenziale_eur_mq"],
            "ratio": _senza_note(mkt["ratio_per_tipologia"]),
            "agricolo": _senza_note(mkt["terreno_agricolo_eur_mq_per_regione"]),
            "trend": _senza_note(mkt["trend_annuo_per_provincia"]),
            "terreni": _senza_note(mkt["terreni"]),
            "rettifiche": _senza_note(mkt["coefficienti_rettifica"]),
            "fonte": mkt["_meta"]["fonte"],
        },
        "imu": {
            "molt": imu["moltiplicatori_catastali"],
            "rivRendita": imu["rivalutazione_rendita"],
            "rivDominicale": imu["rivalutazione_reddito_dominicale"],
            "aliqRegione": imu["aliquote_default_per_regione"],
            "aliqComune": imu["aliquote_comuni"],
            "rendita": {k: _senza_note(v) for k, v in imu["rendita_stimata_eur_mq"].items()
                        if not k.startswith("_")},
            "renditaComuniA": imu["rendita_stimata_eur_mq"]["fascia_A"]["_comuni"],
            "renditaComuniB": imu["rendita_stimata_eur_mq"]["fascia_B"]["_comuni"],
            "oneri": _senza_note(imu["oneri_gestione_eur_mq_anno"]),
            "moltOneri": _senza_note(imu["moltiplicatore_oneri_per_regione"]),
            "capex": _senza_note(imu["costo_ristrutturazione_eur_mq"]),
            "terreni": _senza_note(imu["imu_terreni"]),
        },
        "ipotesi": _senza_note(config.ipotesi_default()),
    }

    esempio = RADICE / "samples" / "pool_esempio.xlsx"
    if esempio.exists():
        immobili, _ = carica_file(esempio, 0)
        dati["esempio"] = [
            {c: getattr(i, c) for c in CAMPI_ESEMPIO
             if getattr(i, c) not in (None, "", "sconosciuto", 0)}
            for i in immobili
        ]
    else:
        dati["esempio"] = []
    return dati


def main() -> int:
    if not PAGINA.exists():
        print(f"Pagina non trovata: {PAGINA}", file=sys.stderr)
        return 1

    blocco = json.dumps(costruisci(), ensure_ascii=False, separators=(",", ":"))
    testo = PAGINA.read_text(encoding="utf-8")
    nuovo, sostituzioni = re.subn(r"^const D = \{.*\};$", f"const D = {blocco};",
                                  testo, count=1, flags=re.MULTILINE)
    if not sostituzioni:
        print("Blocco 'const D = {...};' non trovato nella pagina.", file=sys.stderr)
        return 1

    PAGINA.write_text(nuovo, encoding="utf-8")
    print(f"Aggiornati {len(blocco)} byte di dati in {PAGINA.relative_to(RADICE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
