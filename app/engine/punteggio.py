"""Semaforo verde/giallo/rosso, punteggio di priorita' e confidenza del dato."""
from __future__ import annotations

from app.models import Immobile

# Peso di ogni elemento nella confidenza complessiva del prospetto
_PESI_CONFIDENZA = {
    "prezzo_base": 0.28,
    "superficie": 0.22,
    "provincia": 0.18,
    "fab": 0.10,
    "stato_conservazione": 0.08,
    "stato_occupazione": 0.06,
    "comparabile": 0.08,
}

_AFFIDABILITA_COMPARABILE = {"alta": 1.0, "media": 0.6, "bassa": 0.25}


def calcola_confidenza(imm: Immobile, comp) -> float:
    """0-1: quanto ci possiamo fidare del prospetto, dati i campi effettivamente letti."""
    punti = 0.0
    if imm.prezzo_base:
        punti += _PESI_CONFIDENZA["prezzo_base"]
    if imm.superficie_mq:
        punti += _PESI_CONFIDENZA["superficie"]
    if imm.provincia:
        punti += _PESI_CONFIDENZA["provincia"]
    if imm.fab is not None:
        punti += _PESI_CONFIDENZA["fab"]
    if imm.stato_conservazione != "sconosciuto":
        punti += _PESI_CONFIDENZA["stato_conservazione"]
    if imm.stato_occupazione != "sconosciuto":
        punti += _PESI_CONFIDENZA["stato_occupazione"]
    punti += _PESI_CONFIDENZA["comparabile"] * _AFFIDABILITA_COMPARABILE.get(
        getattr(comp, "affidabilita", "bassa"), 0.25
    )
    if imm.rendita_catastale:
        punti = min(1.0, punti + 0.04)
    return round(min(1.0, punti), 3)


def assegna_semaforo(p, imm: Immobile, ipotesi: dict) -> None:
    """Classifica l'operazione e spiega il perche' in ``p.motivazioni``."""
    soglie = ipotesi["soglie_semaforo"]
    verde, giallo = soglie["verde"], soglie["giallo"]
    motivi: list[str] = []

    supera_verde = (
        p.multiplo >= verde["multiplo_min"]
        and p.roi >= verde["roi_min"]
        and p.utile >= verde["utile_min"]
    )
    supera_giallo = (
        p.multiplo >= giallo["multiplo_min"]
        and p.roi >= giallo["roi_min"]
        and p.utile >= giallo["utile_min"]
    )

    if supera_verde:
        semaforo = "verde"
        motivi.append(f"Multiplo {p.multiplo:.2f}x e ROI {p.roi:.0%} sopra le soglie di priorita'.")
    elif supera_giallo:
        semaforo = "giallo"
        motivi.append(f"Multiplo {p.multiplo:.2f}x: margine presente ma non prioritario.")
    else:
        semaforo = "rosso"
        if p.utile <= 0:
            motivi.append(f"Operazione in perdita: {p.utile:,.0f} EUR.".replace(",", "."))
        else:
            motivi.append(f"Multiplo {p.multiplo:.2f}x sotto la soglia minima "
                          f"({giallo['multiplo_min']:.2f}x).")

    # Declassamenti per rischio, non per redditivita'
    if imm.stato_occupazione == "occupato_senza_titolo" and semaforo == "verde":
        semaforo = "giallo"
        motivi.append("Declassato: occupazione senza titolo, tempi e costi di rilascio incerti.")
    if imm.stato_occupazione == "occupato" and semaforo == "verde":
        motivi.append("Immobile occupato: verificare scadenza contratto e prelazione del conduttore.")
    if soglie.get("penalita_confidenza_bassa") and p.confidenza < 0.5 and semaforo == "verde":
        semaforo = "giallo"
        motivi.append(f"Declassato: dati incompleti (confidenza {p.confidenza:.0%}), da verificare.")
    if not imm.prezzo_base:
        semaforo = "rosso"
        motivi.append("Nessun prezzo nel file: prospetto non calcolabile.")

    p.semaforo = semaforo
    p.motivazioni = motivi

    # Punteggio 0-100 per ordinare le opportunita' dentro la stessa fascia
    punteggio_multiplo = min(p.multiplo / 3.0, 1.0) * 45 if p.multiplo > 0 else 0
    punteggio_roi = min(max(p.roi, 0) / 1.0, 1.0) * 25
    punteggio_utile = min(max(p.utile, 0) / 150000, 1.0) * 20
    punteggio_confidenza = p.confidenza * 10
    p.punteggio = round(
        punteggio_multiplo + punteggio_roi + punteggio_utile + punteggio_confidenza, 1
    )


def riepilogo(prospetti: list) -> dict:
    """Aggregati di portafoglio per le KPI in testa alla dashboard."""
    if not prospetti:
        return {
            "numero": 0, "verdi": 0, "gialli": 0, "rossi": 0,
            "investimento_totale": 0.0, "incasso_netto": 0.0, "utile": 0.0,
            "multiplo_medio": 0.0, "roi_medio": 0.0, "confidenza_media": 0.0,
            "prezzo_base_totale": 0.0,
        }
    investimento = sum(p.investimento_totale for p in prospetti)
    incasso = sum(p.incasso_netto for p in prospetti)
    utile = incasso - investimento
    return {
        "numero": len(prospetti),
        "verdi": sum(1 for p in prospetti if p.semaforo == "verde"),
        "gialli": sum(1 for p in prospetti if p.semaforo == "giallo"),
        "rossi": sum(1 for p in prospetti if p.semaforo == "rosso"),
        "investimento_totale": investimento,
        "incasso_netto": incasso,
        "utile": utile,
        "multiplo_medio": (incasso / investimento) if investimento else 0.0,
        "roi_medio": (utile / investimento) if investimento else 0.0,
        "confidenza_media": sum(p.confidenza for p in prospetti) / len(prospetti),
        "prezzo_base_totale": 0.0,
    }
