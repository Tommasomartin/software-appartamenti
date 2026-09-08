"""Punto di ingresso dell'applicazione."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config, storage
from app.api import router


@asynccontextmanager
async def ciclo_di_vita(app: FastAPI) -> AsyncIterator[None]:
    storage.inizializza()
    yield


app = FastAPI(
    title="Prospetto Immobili",
    description=(
        "Analisi di pool immobiliari: sconto per classe FAB, costi di acquisto e "
        "mantenimento calibrati per zona, comparabili di mercato e semaforo delle opportunita'."
    ),
    version="1.0.0",
    lifespan=ciclo_di_vita,
)

app.include_router(router)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/salute", include_in_schema=False)
def salute() -> dict:
    return {"stato": "ok"}
