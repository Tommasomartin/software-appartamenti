"""Test degli endpoint HTTP, su database temporaneo."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    config.UPLOAD_DIR.mkdir(exist_ok=True)

    from fastapi.testclient import TestClient

    from app import storage
    from app.main import app

    storage.inizializza()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def pool(client):
    percorso = RADICE / "samples" / "pool_esempio.xlsx"
    if not percorso.exists():
        pytest.skip("file di esempio non generato")
    with open(percorso, "rb") as fh:
        risposta = client.post("/api/carica", files={"file": ("pool_esempio.xlsx", fh)})
    assert risposta.status_code == 200, risposta.text
    return risposta.json()


def test_salute(client):
    assert client.get("/salute").json() == {"stato": "ok"}


def test_dashboard_vuota(client):
    dati = client.get("/api/dashboard").json()
    assert dati["righe"] == []
    assert dati["riepilogo"]["numero"] == 0


def test_caricamento_pool(pool):
    assert pool["immobili_importati"] == 18
    assert pool["diagnostica"][0]["colonne_riconosciute"]["prezzo_base"]


def test_formato_non_supportato(client):
    risposta = client.post("/api/carica", files={"file": ("note.docx", b"x")})
    assert risposta.status_code == 400
    assert "non supportato" in risposta.json()["detail"]


def test_file_illeggibile_non_lascia_portafogli_orfani(client):
    client.post("/api/carica", files={"file": ("vuoto.csv", b"")})
    assert client.get("/api/portafogli").json() == []


def test_dashboard_completa(client, pool):
    dati = client.get("/api/dashboard?orizzonte_mesi=12").json()
    assert len(dati["righe"]) == 18
    riepilogo = dati["riepilogo"]
    assert riepilogo["verdi"] + riepilogo["gialli"] + riepilogo["rossi"] == 18
    # Ordinamento per punteggio decrescente
    punteggi = [r["prospetto"]["punteggio"] for r in dati["righe"]]
    assert punteggi == sorted(punteggi, reverse=True)


def test_ogni_riga_ha_i_link_di_mappa(client, pool):
    for riga in client.get("/api/dashboard").json()["righe"]:
        link = riga["link"]
        assert link["google_maps"].startswith("https://www.google.com/maps")
        assert link["google_earth"].startswith("https://earth.google.com")


def test_orizzonte_piu_lungo_riduce_l_utile(client, pool):
    breve = client.get("/api/dashboard?orizzonte_mesi=3").json()["riepilogo"]
    lungo = client.get("/api/dashboard?orizzonte_mesi=36").json()["riepilogo"]
    assert lungo["utile"] < breve["utile"]
    assert lungo["investimento_totale"] > breve["investimento_totale"]


def test_correzione_manuale_ricalcola(client, pool):
    """Raddoppiando i mq raddoppia la stima di mercato; il prezzo del file no."""
    righe = client.get("/api/dashboard").json()["righe"]
    riga = next(r for r in righe if r["immobile"]["tipologia"] == "residenziale")
    identificativo = riga["immobile"]["id"]
    prima = riga["prospetto"]["prezzo_uscita_da_mercato"]

    dopo = client.patch(
        f"/api/immobile/{identificativo}",
        json={"superficie_mq": riga["immobile"]["superficie_mq"] * 2},
    ).json()
    assert dopo["prospetto"]["prezzo_uscita_da_mercato"] > prima * 1.8


def test_correzione_del_prezzo_sposta_la_rivendita(client, pool):
    """Con il metodo 'file' la rivendita segue il valore a base d'asta."""
    riga = client.get("/api/dashboard").json()["righe"][0]
    dopo = client.patch(
        f"/api/immobile/{riga['immobile']['id']}", json={"prezzo_base": 200_000}
    ).json()
    assert dopo["prospetto"]["prezzo_uscita"] == pytest.approx(140_000)


def test_correzione_valore_non_valido(client, pool):
    identificativo = client.get("/api/dashboard").json()["righe"][0]["immobile"]["id"]
    risposta = client.patch(f"/api/immobile/{identificativo}", json={"superficie_mq": "tanti"})
    assert risposta.status_code == 400


def test_immobile_inesistente(client):
    assert client.get("/api/immobile/non-esiste").status_code == 404


def test_modifica_ipotesi_si_riflette_sul_portafoglio(client, pool):
    prima = client.get("/api/dashboard").json()["riepilogo"]["investimento_totale"]
    client.put("/api/ipotesi", json={"fab": {"scala": {"1": 0.10}}})
    dopo = client.get("/api/dashboard").json()["riepilogo"]["investimento_totale"]
    assert dopo < prima

    client.post("/api/ipotesi/reset")
    ripristinato = client.get("/api/dashboard").json()["riepilogo"]["investimento_totale"]
    assert ripristinato == pytest.approx(prima)


def test_ipotesi_parziali_non_cancellano_le_altre(client):
    client.put("/api/ipotesi", json={"uscita": {"commissione_agenzia_vendita_pct": 0.03}})
    ipotesi = client.get("/api/ipotesi").json()
    assert ipotesi["uscita"]["commissione_agenzia_vendita_pct"] == 0.03
    assert "sconto_trattativa_pct" in ipotesi["uscita"]
    assert ipotesi["acquisto"]["imposta_registro_pct"] == 0.02


def test_esportazione_excel(client, pool):
    risposta = client.get("/api/esporta.xlsx")
    assert risposta.status_code == 200
    assert "spreadsheetml" in risposta.headers["content-type"]
    assert len(risposta.content) > 5000


def test_esportazione_senza_dati(client):
    assert client.get("/api/esporta.xlsx").status_code == 404


def test_eliminazione_portafoglio(client, pool):
    client.delete(f"/api/portafogli/{pool['portafoglio_id']}")
    assert client.get("/api/dashboard").json()["riepilogo"]["numero"] == 0


def test_comparabili_utente_hanno_la_precedenza(client, pool, tmp_path, monkeypatch):
    from app.engine import comparabili

    percorso = tmp_path / "comparabili.csv"
    monkeypatch.setattr(comparabili, "PERCORSO_CSV_UTENTE", percorso)

    csv = ("provincia,comune,tipologia,eur_mq,eur_mq_min,eur_mq_max,variazione_annua,fonte,data\n"
           "MI,Milano,residenziale,9000,7000,12000,0.05,Rilevazione mia,2026-01\n")
    risposta = client.post("/api/comparabili", files={"file": ("c.csv", csv.encode())})
    assert risposta.json()["righe_caricate"] == 1

    righe = client.get("/api/dashboard").json()["righe"]
    milanesi = [r for r in righe
                if r["immobile"]["comune"] == "Milano" and r["immobile"]["tipologia"] == "residenziale"]
    assert milanesi
    assert all(r["prospetto"]["valore_mercato_eur_mq"] == 9000 for r in milanesi)
    assert all("Rilevazione mia" in r["prospetto"]["comparabili"]["fonte"] for r in milanesi)


def test_comparabili_csv_non_valido(client, tmp_path, monkeypatch):
    from app.engine import comparabili
    monkeypatch.setattr(comparabili, "PERCORSO_CSV_UTENTE", tmp_path / "c.csv")
    risposta = client.post("/api/comparabili", files={"file": ("c.csv", b"a,b,c\n1,2,3\n")})
    assert risposta.status_code == 400


def test_riferimenti_dichiarano_la_fonte(client):
    rif = client.get("/api/riferimenti").json()
    assert "STIMA_INTERNA" in rif["mercato"]["fonte"]
    assert rif["imu"]["avvertenza"]
