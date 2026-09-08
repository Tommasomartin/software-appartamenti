"""Schema canonico di un immobile e del suo prospetto economico."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

TIPOLOGIE = (
    "residenziale", "ufficio", "ricettivo", "capannone",
    "commerciale", "box", "terreno", "altro",
)

STATI_OCCUPAZIONE = (
    "libero", "occupato", "occupato_senza_titolo",
    "parzialmente_occupato", "sconosciuto",
)

STATI_CONSERVAZIONE = (
    "nuovo", "buono", "da_ristrutturare",
    "da_ristrutturare_totale", "grezzo", "sconosciuto",
)

DESTINAZIONI_TERRENO = ("edificabile", "agricolo", "industriale", "sconosciuto")


@dataclass
class Immobile:
    """Riga normalizzata del pool, indipendente dal formato del file sorgente."""

    id: str = ""
    portafoglio_id: int = 0
    lotto: str = ""
    fab: int | None = None
    fab_raw: str = ""
    tipologia: str = "altro"

    # Localizzazione
    indirizzo: str = ""
    comune: str = ""
    provincia: str = ""
    regione: str = ""
    cap: str = ""
    lat: float | None = None
    lng: float | None = None

    # Consistenza
    superficie_mq: float | None = None
    vani: float | None = None
    piano: str = ""
    categoria_catastale: str = ""
    foglio: str = ""
    particella: str = ""
    subalterno: str = ""
    rendita_catastale: float | None = None

    # Stato
    stato_occupazione: str = "sconosciuto"
    stato_conservazione: str = "sconosciuto"
    canone_annuo: float | None = None
    destinazione_terreno: str = "sconosciuto"
    indice_edificabilita: float | None = None

    # Prezzo dal file
    prezzo_base: float | None = None
    prezzo_perizia: float | None = None

    note: str = ""
    warning_ingest: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def e_terreno(self) -> bool:
        return self.tipologia == "terreno"

    def indirizzo_completo(self) -> str:
        parti = [p for p in (self.indirizzo, self.cap, self.comune, self.provincia) if p]
        return ", ".join(parti)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Prospetto:
    """Risultato del calcolo economico su un singolo immobile."""

    immobile_id: str = ""

    # Acquisto
    percentuale_acquisto: float = 0.0
    prezzo_acquisto: float = 0.0
    intermediazione: float = 0.0
    percentuale_esborso_totale: float = 0.0
    imposta_registro: float = 0.0
    imposte_fisse: float = 0.0
    notaio: float = 0.0
    commissione_acquisto: float = 0.0
    altri_costi_acquisto: float = 0.0
    totale_costi_acquisto: float = 0.0
    capex_ristrutturazione: float = 0.0
    cassa_iniziale: float = 0.0

    # Mantenimento
    imu_annua: float = 0.0
    imu_metodo: str = ""
    oneri_annui: float = 0.0
    oneri_dettaglio: dict[str, float] = field(default_factory=dict)
    ricavo_locazione_annuo: float = 0.0
    mantenimento_netto_annuo: float = 0.0
    mantenimento_per_orizzonte: dict[str, float] = field(default_factory=dict)

    # Uscita
    valore_mercato_eur_mq: float = 0.0
    comparabili: dict[str, Any] = field(default_factory=dict)
    valore_mercato_lordo: float = 0.0
    coefficienti_applicati: dict[str, float] = field(default_factory=dict)
    metodo_uscita: str = ""
    prezzo_uscita_da_file: float = 0.0
    prezzo_uscita_da_mercato: float = 0.0
    prezzo_uscita: float = 0.0
    commissione_vendita: float = 0.0
    costi_uscita: float = 0.0
    tassazione_plusvalenza: float = 0.0
    incasso_netto: float = 0.0

    # Sintesi
    orizzonte_mesi: int = 12
    investimento_totale: float = 0.0
    utile: float = 0.0
    multiplo: float = 0.0
    roi: float = 0.0
    roi_annualizzato: float = 0.0
    margine_su_ricavo: float = 0.0
    prezzo_pareggio: float = 0.0

    semaforo: str = "rosso"
    punteggio: float = 0.0
    confidenza: float = 0.0
    motivazioni: list[str] = field(default_factory=list)
    warning: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
