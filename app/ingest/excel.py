"""Lettura di file Excel/CSV con individuazione automatica della riga di intestazione."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.ingest.mapping import SINONIMI, slug

# Tutti gli alias conosciuti: servono a capire quale riga e' l'intestazione
_ALIAS_NOTI = {a for alias in SINONIMI.values() for a in alias}


def _punteggio_intestazione(valori: list[object]) -> int:
    """Quante celle di questa riga somigliano a un'intestazione conosciuta."""
    punti = 0
    for v in valori:
        s = slug(v)
        if not s:
            continue
        if s in _ALIAS_NOTI or any(a in s or s in a for a in _ALIAS_NOTI):
            punti += 1
    return punti


def _trova_riga_intestazione(df: pd.DataFrame, max_righe: int = 15) -> int:
    """Indice della riga da usare come header (i pool hanno spesso righe di titolo)."""
    migliore, punteggio_migliore = 0, -1
    for i in range(min(max_righe, len(df))):
        valori = list(df.iloc[i].values)
        non_vuote = sum(1 for v in valori if str(v).strip() not in ("", "nan", "None"))
        if non_vuote < 2:
            continue
        p = _punteggio_intestazione(valori)
        if p > punteggio_migliore:
            migliore, punteggio_migliore = i, p
    return migliore if punteggio_migliore >= 2 else 0


def _pulisci(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    colonne, visti = [], {}
    for c in df.columns:
        nome = str(c).strip()
        if nome.lower().startswith("unnamed") or nome in ("", "nan"):
            nome = f"colonna_{len(colonne) + 1}"
        if nome in visti:
            visti[nome] += 1
            nome = f"{nome}_{visti[nome]}"
        else:
            visti[nome] = 0
        colonne.append(nome)
    df.columns = colonne
    return df


def leggi(percorso: Path) -> list[tuple[str, pd.DataFrame]]:
    """Restituisce [(nome_foglio, dataframe), ...] normalizzati."""
    suffisso = percorso.suffix.lower()
    fogli: list[tuple[str, pd.DataFrame]] = []

    if suffisso in {".csv", ".txt", ".tsv"}:
        for sep in (";", ",", "\t", "|"):
            try:
                grezzo = pd.read_csv(percorso, sep=sep, header=None, dtype=object,
                                     engine="python", on_bad_lines="skip")
            except Exception:
                continue
            if grezzo.shape[1] > 1:
                fogli.append((percorso.stem, grezzo))
                break
        else:
            fogli.append((percorso.stem, pd.read_csv(percorso, header=None, dtype=object)))
    else:
        motore = "openpyxl" if suffisso in {".xlsx", ".xlsm", ".xltx"} else None
        libro = pd.read_excel(percorso, sheet_name=None, header=None, dtype=object, engine=motore)
        fogli = list(libro.items())

    risultato: list[tuple[str, pd.DataFrame]] = []
    for nome, grezzo in fogli:
        if grezzo is None or grezzo.empty:
            continue
        riga = _trova_riga_intestazione(grezzo)
        df = grezzo.iloc[riga + 1:].copy()
        df.columns = [str(c) for c in grezzo.iloc[riga].values]
        df = _pulisci(df)
        if not df.empty and len(df.columns) >= 2:
            risultato.append((str(nome), df))
    return risultato
