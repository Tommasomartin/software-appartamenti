"""Genera un pool di esempio con le imperfezioni tipiche dei file dei fondi."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RADICE = Path(__file__).resolve().parent.parent

RIGHE = [
    # Lotto, FAB, Tipologia, Indirizzo, Comune, Prov, Sup, Stato occ., Stato cons., Cat, Rendita, Canone, Prezzo base
    ("L-001", "FAB 1", "Appartamento", "Via Ripamonti 122", "Milano", "MI", "95", "Libero", "Da ristrutturare", "A/2", "1.150,00", "", "420.000,00"),
    ("L-002", "FAB 2", "Appartamento", "Via Padova 44", "Milano", "MI", "72", "Occupato", "Buono", "A/3", "890,00", "9.600,00", "295.000,00"),
    ("L-003", "FAB 3", "Ufficio", "Corso Vittorio Emanuele 8", "Torino", "TO", "180", "Occupato", "Sano", "A/10", "3.200,00", "16.800,00", "310.000,00"),
    ("L-004", "FAB 4", "Negozio", "Via Roma 15", "Bologna", "BO", "110", "Libero", "Da rifare", "C/1", "2.900,00", "", "265.000,00"),
    ("L-005", "FAB 5", "Capannone industriale", "Via dell'Industria 3", "Brescia", "BS", "1.500", "Libero", "Buono", "D/7", "", "", "620.000,00"),
    ("L-006", "FAB 6", "Capannone", "Zona ASI lotto 7", "Foggia", "FG", "2.200", "Occupato", "Da ristrutturare", "D/7", "", "31.000,00", "480.000,00"),
    ("L-007", "FAB 7", "Hotel 3 stelle", "Lungomare Colombo 21", "Rimini", "RN", "820", "Libero", "Da ristrutturare totalmente", "D/2", "", "", "1.850.000,00"),
    ("L-008", "FAB 8", "B&B / affittacamere", "Via Garibaldi 9", "Lecce", "LE", "260", "Occupato", "Buono", "D/2", "", "22.000,00", "410.000,00"),
    ("L-009", "FAB 9", "Villetta a schiera", "Via dei Pini 4", "Como", "CO", "140", "Libero", "Nuovo", "A/7", "1.480,00", "", "395.000,00"),
    ("L-010", "FAB 10", "Appartamento", "Via Toledo 200", "Napoli", "NA", "88", "Occupato senza titolo", "Da ristrutturare", "A/3", "1.020,00", "", "230.000,00"),
    ("T-011", "FAB 1", "Terreno edificabile", "Localita' Cerreto", "Lecce", "LE", "4.000", "Libero", "", "", "", "", "180.000,00"),
    ("T-012", "FAB 3", "Terreno agricolo", "Contrada Serre", "Alba", "CN", "22.000", "Libero", "", "", "", "", "52.000,00"),
    ("T-013", "FAB 5", "Terreno industriale", "Via Artigiani snc", "Modena", "MO", "8.500", "Libero", "", "", "", "", "340.000,00"),
    ("L-014", "FAB 2", "Box auto", "Via Bligny 12", "Milano", "MI", "18", "Libero", "Buono", "C/6", "215,00", "", "42.000,00"),
    ("L-015", "FAB 7", "Ufficio direzionale", "Viale Europa 55", "Roma", "RM", "240", "Libero", "Buono", "A/10", "5.100,00", "", "690.000,00"),
    ("L-016", "FAB 4", "Appartamento", "Via Etnea 300", "Catania", "CT", "105", "Occupato", "Da ristrutturare", "A/3", "760,00", "6.000,00", "135.000,00"),
    ("L-017", "FAB 9", "Magazzino", "Via Portuense 410", "Roma", "RM", "600", "Libero", "Buono", "C/2", "", "", "520.000,00"),
    ("L-018", "FAB 1", "Appartamento", "Via Manzoni 3", "Bergamo", "BG", "110", "Libero", "Da ristrutturare", "A/2", "1.320,00", "", "268.000,00"),
]

INTESTAZIONI = [
    "Lotto", "FAB", "Tipologia", "Indirizzo", "Comune", "Prov.", "Sup. commerciale mq",
    "Stato occupativo", "Stato conservazione", "Cat. catastale", "Rendita catastale",
    "Canone annuo", "Prezzo base d'asta",
]


def genera(destinazione: Path) -> Path:
    corpo = pd.DataFrame(RIGHE, columns=INTESTAZIONI)

    # I file reali hanno righe di titolo sopra l'intestazione: le riproduciamo
    preambolo = pd.DataFrame(
        [["FONDO IMMOBILIARE ESEMPIO - POOL DI VENDITA"] + [""] * (len(INTESTAZIONI) - 1),
         ["Elenco lotti - dati indicativi"] + [""] * (len(INTESTAZIONI) - 1),
         [""] * len(INTESTAZIONI)],
        columns=INTESTAZIONI,
    )
    completo = pd.concat([preambolo, pd.DataFrame([INTESTAZIONI], columns=INTESTAZIONI), corpo],
                         ignore_index=True)

    destinazione.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(destinazione, engine="xlsxwriter") as writer:
        completo.to_excel(writer, sheet_name="Pool", index=False, header=False)
        pd.DataFrame({"Legenda": ["FAB = classe di fabbricato", "Prezzi IVA esclusa"]}).to_excel(
            writer, sheet_name="Legenda", index=False
        )
    return destinazione


if __name__ == "__main__":
    percorso = Path(sys.argv[1]) if len(sys.argv) > 1 else RADICE / "samples" / "pool_esempio.xlsx"
    print("Creato:", genera(percorso))
