"""Estrazione di tabelle da PDF (perizie, elenchi lotti, bandi)."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

from app.ingest.excel import _pulisci, _trova_riga_intestazione

_MAX_PAGINE = 60


def _tabelle(percorso: Path) -> list[pd.DataFrame]:
    tabelle: list[pd.DataFrame] = []
    with pdfplumber.open(percorso) as pdf:
        for pagina in pdf.pages[:_MAX_PAGINE]:
            for grezza in pagina.extract_tables() or []:
                if len(grezza) < 2 or len(grezza[0]) < 2:
                    continue
                df = pd.DataFrame(grezza).map(
                    lambda v: re.sub(r"\s+", " ", str(v)).strip() if v is not None else None
                )
                riga = _trova_riga_intestazione(df)
                corpo = df.iloc[riga + 1:].copy()
                corpo.columns = [str(c) for c in df.iloc[riga].values]
                corpo = _pulisci(corpo)
                if not corpo.empty:
                    tabelle.append(corpo)
    return tabelle


def _unisci_compatibili(tabelle: list[pd.DataFrame]) -> list[pd.DataFrame]:
    """Le tabelle spezzate su piu' pagine hanno le stesse colonne: le ricompone."""
    gruppi: dict[tuple, pd.DataFrame] = {}
    for df in tabelle:
        chiave = tuple(df.columns)
        gruppi[chiave] = pd.concat([gruppi[chiave], df], ignore_index=True) if chiave in gruppi else df
    return list(gruppi.values())


_CAMPI_TESTO = [
    ("lotto", r"(?:lotto|lot)\s*[:n°#.]*\s*([A-Za-z0-9\-/]+)"),
    ("fab_raw", r"\b(fab(?:bricato)?\s*[-_.:n°#]*\s*\d{1,2})\b"),
    ("comune", r"comune\s*(?:di)?\s*[:.]?\s*([A-Za-zÀ-ÿ'\s]{3,40})"),
    ("indirizzo", r"(?:indirizzo|ubicazione|sito in)\s*[:.]?\s*([^\n]{5,80})"),
    ("superficie_mq", r"(?:superficie|sup\.?)\s*(?:commerciale|lorda|utile)?\s*[:.]?\s*([\d.,]+)\s*(?:mq|m2|m²)"),
    ("prezzo_base", r"(?:prezzo base|base d'?asta|valore)\s*[:.]?\s*(?:€|eur)?\s*([\d.,]+)"),
    ("rendita_catastale", r"rendita\s*(?:catastale)?\s*[:.]?\s*(?:€|eur)?\s*([\d.,]+)"),
]


def _da_testo(percorso: Path) -> pd.DataFrame:
    """Fallback per PDF senza tabelle: estrae i campi con espressioni regolari."""
    righe: list[dict] = []
    with pdfplumber.open(percorso) as pdf:
        for numero_pagina, pagina in enumerate(pdf.pages[:_MAX_PAGINE], start=1):
            testo = pagina.extract_text() or ""
            if not testo.strip():
                continue
            riga: dict[str, object] = {"pagina_pdf": numero_pagina}
            for campo, pattern in _CAMPI_TESTO:
                m = re.search(pattern, testo, re.IGNORECASE)
                if m:
                    riga[campo] = m.group(1).strip()
            if len(riga) > 2:
                riga["note"] = testo[:400]
                righe.append(riga)
    return pd.DataFrame(righe)


def leggi(percorso: Path) -> list[tuple[str, pd.DataFrame]]:
    tabelle = _unisci_compatibili(_tabelle(percorso))
    if tabelle:
        return [(f"{percorso.stem} - tabella {i + 1}", df) for i, df in enumerate(tabelle)]
    testo = _da_testo(percorso)
    return [(f"{percorso.stem} - testo", testo)] if not testo.empty else []
