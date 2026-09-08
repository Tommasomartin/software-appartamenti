"""Persistenza su SQLite: portafogli caricati, immobili e ipotesi correnti."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app import config
from app.models import Immobile

SCHEMA = """
CREATE TABLE IF NOT EXISTS portafogli (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    file_origine TEXT NOT NULL,
    caricato_il TEXT NOT NULL,
    diagnostica TEXT NOT NULL DEFAULT '[]',
    numero_immobili INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS immobili (
    id TEXT PRIMARY KEY,
    portafoglio_id INTEGER NOT NULL,
    dati TEXT NOT NULL,
    FOREIGN KEY (portafoglio_id) REFERENCES portafogli(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_immobili_portafoglio ON immobili(portafoglio_id);
CREATE TABLE IF NOT EXISTS impostazioni (
    chiave TEXT PRIMARY KEY,
    valore TEXT NOT NULL
);
"""


def connessione() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inizializza() -> None:
    with connessione() as conn:
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------- portafogli

def crea_portafoglio(nome: str, file_origine: str) -> int:
    with connessione() as conn:
        cur = conn.execute(
            "INSERT INTO portafogli (nome, file_origine, caricato_il) VALUES (?, ?, ?)",
            (nome, file_origine, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        return int(cur.lastrowid)


def aggiorna_portafoglio(portafoglio_id: int, diagnostica: list, numero: int) -> None:
    with connessione() as conn:
        conn.execute(
            "UPDATE portafogli SET diagnostica = ?, numero_immobili = ? WHERE id = ?",
            (json.dumps(diagnostica, ensure_ascii=False), numero, portafoglio_id),
        )


def elenca_portafogli() -> list[dict]:
    with connessione() as conn:
        righe = conn.execute(
            "SELECT * FROM portafogli ORDER BY id DESC"
        ).fetchall()
    return [
        {**dict(r), "diagnostica": json.loads(r["diagnostica"])} for r in righe
    ]


def elimina_portafoglio(portafoglio_id: int) -> None:
    with connessione() as conn:
        conn.execute("DELETE FROM immobili WHERE portafoglio_id = ?", (portafoglio_id,))
        conn.execute("DELETE FROM portafogli WHERE id = ?", (portafoglio_id,))


# ----------------------------------------------------------------- immobili

def salva_immobili(immobili: list[Immobile]) -> None:
    with connessione() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO immobili (id, portafoglio_id, dati) VALUES (?, ?, ?)",
            [
                (i.id, i.portafoglio_id, json.dumps(i.to_dict(), ensure_ascii=False, default=str))
                for i in immobili
            ],
        )


def _da_riga(riga: sqlite3.Row) -> Immobile:
    dati = json.loads(riga["dati"])
    campi = {f for f in Immobile.__dataclass_fields__}
    return Immobile(**{k: v for k, v in dati.items() if k in campi})


def carica_immobili(portafoglio_id: int | None = None) -> list[Immobile]:
    with connessione() as conn:
        if portafoglio_id is None:
            righe = conn.execute("SELECT * FROM immobili").fetchall()
        else:
            righe = conn.execute(
                "SELECT * FROM immobili WHERE portafoglio_id = ?", (portafoglio_id,)
            ).fetchall()
    return [_da_riga(r) for r in righe]


def carica_immobile(immobile_id: str) -> Immobile | None:
    with connessione() as conn:
        riga = conn.execute("SELECT * FROM immobili WHERE id = ?", (immobile_id,)).fetchone()
    return _da_riga(riga) if riga else None


def aggiorna_immobile(immobile: Immobile) -> None:
    with connessione() as conn:
        conn.execute(
            "UPDATE immobili SET dati = ? WHERE id = ?",
            (json.dumps(immobile.to_dict(), ensure_ascii=False, default=str), immobile.id),
        )


# -------------------------------------------------------------- impostazioni

def _fondi(base: dict, sopra: dict) -> dict:
    """Merge ricorsivo: le chiavi salvate sovrascrivono i default, il resto resta."""
    risultato = dict(base)
    for chiave, valore in sopra.items():
        if isinstance(valore, dict) and isinstance(risultato.get(chiave), dict):
            risultato[chiave] = _fondi(risultato[chiave], valore)
        else:
            risultato[chiave] = valore
    return risultato


def leggi_ipotesi() -> dict:
    default = json.loads(json.dumps(config.ipotesi_default()))
    with connessione() as conn:
        riga = conn.execute(
            "SELECT valore FROM impostazioni WHERE chiave = 'ipotesi'"
        ).fetchone()
    return _fondi(default, json.loads(riga["valore"])) if riga else default


def salva_ipotesi(ipotesi: dict[str, Any]) -> dict:
    unite = _fondi(leggi_ipotesi(), ipotesi)
    with connessione() as conn:
        conn.execute(
            "INSERT INTO impostazioni (chiave, valore) VALUES ('ipotesi', ?) "
            "ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore",
            (json.dumps(unite, ensure_ascii=False),),
        )
    return unite


def azzera_ipotesi() -> dict:
    with connessione() as conn:
        conn.execute("DELETE FROM impostazioni WHERE chiave = 'ipotesi'")
    return leggi_ipotesi()
