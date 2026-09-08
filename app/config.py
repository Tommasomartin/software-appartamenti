"""Percorsi e caricamento dei dataset di riferimento."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
ROOT_DIR = BASE_DIR.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
DB_PATH = ROOT_DIR / "portafoglio.db"

UPLOAD_DIR.mkdir(exist_ok=True)


def _load(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def geografia() -> dict:
    return _load("geografia.json")


@lru_cache(maxsize=None)
def imu_oneri() -> dict:
    return _load("imu_oneri.json")


@lru_cache(maxsize=None)
def mercato() -> dict:
    return _load("mercato.json")


@lru_cache(maxsize=None)
def ipotesi_default() -> dict:
    return _load("ipotesi_default.json")


def ricarica_dataset() -> None:
    """Svuota la cache dopo una modifica ai file JSON di riferimento."""
    for fn in (geografia, imu_oneri, mercato, ipotesi_default):
        fn.cache_clear()
