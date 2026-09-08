"""Test del motore di calcolo e dell'ingestione."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from app import config
from app.engine import comparabili, costi, valutazione
from app.ingest import mapping
from app.ingest.normalizza import carica_file
from app.models import Immobile


@pytest.fixture
def ipotesi() -> dict:
    import json
    return json.loads(json.dumps(config.ipotesi_default()))


def immobile(**kwargs) -> Immobile:
    base = dict(
        id="test", tipologia="residenziale", comune="Milano", provincia="MI",
        regione="Lombardia", superficie_mq=100.0, prezzo_base=300000.0,
        stato_occupazione="libero", stato_conservazione="buono", fab=1,
    )
    return Immobile(**{**base, **kwargs})


# ----------------------------------------------------------------- parser

@pytest.mark.parametrize("grezzo,atteso", [
    ("€ 1.250.000,50", 1250000.50),
    ("1,250,000.50", 1250000.50),
    ("250 mq", 250.0),
    ("3.500", 3500.0),
    ("12,5", 12.5),
    ("1.234.567", 1234567.0),
    ("n.d.", None),
    ("", None),
    (None, None),
])
def test_parsing_numeri_italiani_e_inglesi(grezzo, atteso):
    assert mapping.numero(grezzo) == atteso


@pytest.mark.parametrize("testo,atteso", [
    ("Lotto FAB-07 Milano", 7),
    ("FAB 3", 3),
    ("fabbricato n. 10", 10),
    ("FAB 11", None),      # fuori scala
    ("nessun codice", None),
])
def test_estrazione_fab(testo, atteso):
    assert mapping.estrai_fab(testo)[0] == atteso


@pytest.mark.parametrize("testo,atteso", [
    ("Capannone industriale", "capannone"),
    ("Terreno agricolo", "terreno"),
    ("Hotel 3 stelle", "ricettivo"),
    ("Ufficio direzionale", "ufficio"),
    ("Appartamento", "residenziale"),
    ("Negozio", "commerciale"),
    ("Box auto", "box"),
])
def test_classificazione_tipologia(testo, atteso):
    assert mapping.classifica_tipologia(testo) == atteso


@pytest.mark.parametrize("testo,atteso", [
    ("Libero", "libero"),
    ("OCCUPATO da conduttore", "occupato"),
    ("occupato senza titolo", "occupato_senza_titolo"),
    ("sfitto", "libero"),
])
def test_classificazione_occupazione(testo, atteso):
    assert mapping.classifica_occupazione(testo) == atteso


@pytest.mark.parametrize("testo,atteso", [
    ("da rifare", "da_ristrutturare"),
    ("sano", "buono"),
    ("nuova costruzione", "nuovo"),
    ("totalmente da ristrutturare", "da_ristrutturare_totale"),
])
def test_classificazione_conservazione(testo, atteso):
    assert mapping.classifica_conservazione(testo) == atteso


def test_geografia_completa_il_dato_mancante():
    assert mapping.risolvi_geografia("Milano", "", "") == ("Milano", "MI", "Lombardia")
    assert mapping.risolvi_geografia("", "Roma", "")[1] == "RM"
    assert mapping.risolvi_geografia("Seregno", "MB", "")[2] == "Lombardia"


def test_ogni_provincia_ha_un_valore_di_mercato():
    province = set(config.geografia()["province"])
    coperte = set(config.mercato()["residenziale_eur_mq"])
    assert province <= coperte


# -------------------------------------------------------------------- FAB

def test_fab_basso_paga_meno_di_fab_alto(ipotesi):
    basso = valutazione.percentuale_acquisto(immobile(fab=1), ipotesi)
    alto = valutazione.percentuale_acquisto(immobile(fab=10), ipotesi)
    assert basso < alto
    assert basso == pytest.approx(0.30)


def test_scala_fab_monotona(ipotesi):
    scala = ipotesi["fab"]["scala"]
    valori = [scala[str(n)] for n in range(1, 11)]
    assert valori == sorted(valori), "un FAB piu' alto non puo' avere piu' sconto"


def test_fab_assente_usa_il_default(ipotesi):
    assert valutazione.percentuale_acquisto(immobile(fab=None), ipotesi) == pytest.approx(0.50)


# ------------------------------------------------------------------ costi

def test_notaio_cresce_con_il_prezzo(ipotesi):
    valori = [costi.notaio(p, ipotesi) for p in (50_000, 150_000, 400_000, 900_000, 3_000_000)]
    assert valori == sorted(valori)


def test_imposta_registro_e_il_due_percento(ipotesi):
    voci = costi.costi_acquisto(500_000, ipotesi)
    assert voci["imposta_registro"] == pytest.approx(10_000)


def test_imposta_registro_ha_un_minimo(ipotesi):
    voci = costi.costi_acquisto(10_000, ipotesi)
    assert voci["imposta_registro"] == pytest.approx(ipotesi["acquisto"]["imposta_registro_minima"])


def test_imu_con_rendita_reale_usa_il_calcolo_esatto():
    imm = immobile(categoria_catastale="A/2", rendita_catastale=1100.0)
    importo, metodo, dettaglio = costi.imu_annua(imm)
    atteso = 1100 * 1.05 * 160 * 0.0114  # Milano
    assert importo == pytest.approx(atteso)
    assert "esatto" in metodo


def test_imu_stimata_vicina_a_quella_esatta():
    """La stima da mq non deve allontanarsi troppo dal calcolo con rendita reale."""
    esatta, _, _ = costi.imu_annua(immobile(superficie_mq=90, categoria_catastale="A/2",
                                            rendita_catastale=1100.0))
    stimata, _, _ = costi.imu_annua(immobile(superficie_mq=90, categoria_catastale="A/2"))
    assert 0.6 < stimata / esatta < 1.6


def test_imu_varia_per_zona():
    milano, _, _ = costi.imu_annua(immobile(comune="Milano", provincia="MI", regione="Lombardia",
                                            categoria_catastale="A/2", rendita_catastale=1000))
    trento, _, _ = costi.imu_annua(immobile(comune="Trento", provincia="TN",
                                            regione="Trentino-Alto Adige",
                                            categoria_catastale="A/2", rendita_catastale=1000))
    assert milano > trento


def test_tari_non_dovuta_se_libero(ipotesi):
    libero = costi.oneri_annui(immobile(stato_occupazione="libero"), ipotesi)
    occupato = costi.oneri_annui(immobile(stato_occupazione="occupato"), ipotesi)
    assert libero["tari"] == 0
    assert occupato["tari"] > 0


def test_capex_solo_se_da_ristrutturare():
    assert costi.capex_ristrutturazione(immobile(stato_conservazione="buono")) < \
           costi.capex_ristrutturazione(immobile(stato_conservazione="da_ristrutturare"))
    assert costi.capex_ristrutturazione(immobile(stato_conservazione="nuovo")) == 0


# ----------------------------------------------------------- comparabili

def test_serie_temporale_riflette_il_trend():
    c = comparabili.stima(immobile(provincia="MI", comune="Milano"))
    assert c.variazione_annua > 0
    # Mercato in crescita: i prezzi di 12 mesi fa sono piu' bassi di quelli di 3 mesi fa
    assert c.serie["m12"] < c.serie["m6"] < c.serie["m3"]


def test_capannone_vale_meno_del_residenziale_nella_stessa_zona():
    res = comparabili.stima(immobile(tipologia="residenziale")).eur_mq
    cap = comparabili.stima(immobile(tipologia="capannone")).eur_mq
    assert cap < res


def test_terreno_edificabile_dipende_dall_indice():
    basso = comparabili.stima(immobile(tipologia="terreno", destinazione_terreno="edificabile",
                                       indice_edificabilita=0.1)).eur_mq
    alto = comparabili.stima(immobile(tipologia="terreno", destinazione_terreno="edificabile",
                                      indice_edificabilita=0.6)).eur_mq
    assert alto > basso * 5


def test_provincia_ignota_ripiega_sulla_media_nazionale():
    c = comparabili.stima(immobile(provincia="", comune="", regione=""))
    assert c.affidabilita == "bassa"
    assert c.eur_mq > 0


# ------------------------------------------------------------ valutazione

def test_quadratura_del_prospetto(ipotesi):
    p = valutazione.calcola(immobile(), ipotesi, 12)
    # La cassa iniziale e' la somma delle sue componenti
    assert p.cassa_iniziale == pytest.approx(
        p.prezzo_acquisto + p.totale_costi_acquisto + p.capex_ristrutturazione
    )
    # L'utile e' la differenza fra incasso netto e investimento
    assert p.utile == pytest.approx(p.incasso_netto - p.investimento_totale)
    # Il multiplo e' coerente con l'utile
    assert p.multiplo == pytest.approx(p.incasso_netto / p.investimento_totale)


def test_tenere_di_piu_costa_di_piu(ipotesi):
    imm = immobile(stato_occupazione="libero")
    breve = valutazione.calcola(imm, ipotesi, 3)
    lungo = valutazione.calcola(imm, ipotesi, 24)
    assert lungo.investimento_totale > breve.investimento_totale
    assert lungo.utile < breve.utile


def test_immobile_occupato_vale_meno_nella_stima_di_mercato(ipotesi):
    """La regola 'valore file meno 30%' e' piatta; la stima di mercato invece sconta."""
    libero = valutazione.calcola(immobile(stato_occupazione="libero"), ipotesi, 12)
    occupato = valutazione.calcola(immobile(stato_occupazione="occupato"), ipotesi, 12)
    assert occupato.prezzo_uscita_da_mercato < libero.prezzo_uscita_da_mercato
    assert occupato.prezzo_uscita == pytest.approx(libero.prezzo_uscita)


def test_rettifiche_opzionali_sul_metodo_file(ipotesi):
    ipotesi["uscita"]["applica_rettifiche_al_metodo_file"] = True
    libero = valutazione.calcola(immobile(stato_occupazione="libero"), ipotesi, 12)
    occupato = valutazione.calcola(immobile(stato_occupazione="occupato"), ipotesi, 12)
    assert occupato.prezzo_uscita < libero.prezzo_uscita


def test_da_ristrutturare_ha_capex_ma_esce_come_buono(ipotesi):
    p = valutazione.calcola(immobile(stato_conservazione="da_ristrutturare"), ipotesi, 12)
    assert p.capex_ristrutturazione > 0
    assert p.coefficienti_applicati["stato_conservazione"] == pytest.approx(1.0)


def test_prezzo_di_pareggio_azzera_l_utile(ipotesi):
    p = valutazione.calcola(immobile(), ipotesi, 12)
    commissione = ipotesi["uscita"]["commissione_agenzia_vendita_pct"]
    utile_al_pareggio = (
        p.prezzo_pareggio - p.prezzo_pareggio * commissione - p.costi_uscita - p.investimento_totale
    )
    assert utile_al_pareggio == pytest.approx(0, abs=1.0)


def test_provvigione_vendita_e_il_due_percento(ipotesi):
    p = valutazione.calcola(immobile(), ipotesi, 12)
    assert p.commissione_vendita == pytest.approx(p.prezzo_uscita * 0.02)


def test_locazione_riduce_il_costo_di_mantenimento(ipotesi):
    vuoto = valutazione.calcola(immobile(stato_occupazione="libero"), ipotesi, 12)
    affittato = valutazione.calcola(
        immobile(stato_occupazione="occupato", canone_annuo=15000), ipotesi, 12
    )
    assert affittato.mantenimento_netto_annuo < vuoto.mantenimento_netto_annuo


# --------------------------------------------------------------- semaforo

def test_affare_ottimo_e_verde(ipotesi):
    p = valutazione.calcola(immobile(fab=1, prezzo_base=900_000, superficie_mq=200), ipotesi, 12)
    assert p.multiplo > 1.30
    assert p.semaforo == "verde"


def test_multiplo_non_puo_superare_il_tetto_strutturale(ipotesi):
    """Esborso 40% del valore file, rivendita 70%: il tetto assoluto e' 1,75x."""
    for fab in range(1, 11):
        p = valutazione.calcola(immobile(fab=fab, prezzo_base=400_000), ipotesi, 12)
        assert p.multiplo <= 1.75


def test_fab_alto_e_strutturalmente_in_perdita(ipotesi):
    """Con FAB 8 si esborsa il 70% + 10% e si rivende al 70%: non puo' funzionare."""
    p = valutazione.calcola(immobile(fab=8, prezzo_base=400_000), ipotesi, 12)
    assert p.utile < 0
    assert p.semaforo == "rosso"


def test_le_soglie_sono_raggiungibili(ipotesi):
    """Una soglia verde sopra il tetto strutturale renderebbe il semaforo inutile."""
    assert ipotesi["soglie_semaforo"]["verde"]["multiplo_min"] < 1.75


def test_operazione_in_perdita_e_rossa(ipotesi):
    p = valutazione.calcola(immobile(fab=10, prezzo_base=900_000, superficie_mq=60), ipotesi, 12)
    assert p.semaforo == "rosso"


def test_occupazione_senza_titolo_declassa(ipotesi):
    buono = immobile(fab=1, prezzo_base=900_000, superficie_mq=200)
    abusivo = immobile(fab=1, prezzo_base=900_000, superficie_mq=200,
                       stato_occupazione="occupato_senza_titolo")
    assert valutazione.calcola(buono, ipotesi, 12).semaforo == "verde"
    assert valutazione.calcola(abusivo, ipotesi, 12).semaforo != "verde"


def test_senza_prezzo_e_sempre_rosso(ipotesi):
    p = valutazione.calcola(immobile(prezzo_base=None), ipotesi, 12)
    assert p.semaforo == "rosso"


def test_confidenza_scende_se_mancano_dati(ipotesi):
    completo = valutazione.calcola(immobile(rendita_catastale=1000), ipotesi, 12)
    scarno = valutazione.calcola(
        immobile(superficie_mq=None, provincia="", comune="", regione="", fab=None,
                 stato_conservazione="sconosciuto", stato_occupazione="sconosciuto"),
        ipotesi, 12,
    )
    assert scarno.confidenza < completo.confidenza
    assert scarno.confidenza < 0.5


# -------------------------------------------------------------- ingestione

def test_lettura_del_file_di_esempio():
    percorso = RADICE / "samples" / "pool_esempio.xlsx"
    if not percorso.exists():
        pytest.skip("file di esempio non generato")
    immobili, diagnostica = carica_file(percorso, 1)

    assert len(immobili) == 18
    # Il foglio "Legenda" non deve entrare nel portafoglio: viene scartato
    # dal lettore (una sola colonna) o marcato come non utilizzato.
    assert all(
        not d["utilizzato"] for d in diagnostica if d["foglio"] == "Legenda"
    )
    assert all(i.portafoglio_id == 1 for i in immobili)

    per_lotto = {i.lotto: i for i in immobili}
    milano = per_lotto["L-001"]
    assert milano.fab == 1
    assert milano.comune == "Milano" and milano.provincia == "MI" and milano.regione == "Lombardia"
    assert milano.superficie_mq == 95
    assert milano.prezzo_base == 420000
    assert milano.stato_conservazione == "da_ristrutturare"
    assert milano.tipologia == "residenziale"

    assert per_lotto["L-005"].tipologia == "capannone"
    assert per_lotto["L-007"].tipologia == "ricettivo"
    assert per_lotto["T-011"].tipologia == "terreno"
    assert per_lotto["T-011"].destinazione_terreno == "edificabile"
    assert per_lotto["L-010"].stato_occupazione == "occupato_senza_titolo"


def test_intestazione_sotto_le_righe_di_titolo():
    """Il file di esempio ha 3 righe di titolo prima dell'intestazione vera."""
    percorso = RADICE / "samples" / "pool_esempio.xlsx"
    if not percorso.exists():
        pytest.skip("file di esempio non generato")
    _, diagnostica = carica_file(percorso, 1)
    riconosciute = diagnostica[0]["colonne_riconosciute"]
    assert "prezzo_base" in riconosciute
    assert "superficie_mq" in riconosciute
    assert "fab_raw" in riconosciute


# ---------------------------------------------------- intermediazione 10%

def test_intermediazione_si_somma_alla_percentuale_fab(ipotesi):
    """FAB 1 al 30% con intermediazione al 10% => esborso del 40% del valore del file."""
    p = valutazione.calcola(immobile(fab=1, prezzo_base=200_000), ipotesi, 12)
    assert p.prezzo_acquisto == pytest.approx(60_000)
    assert p.intermediazione == pytest.approx(20_000)
    assert p.percentuale_esborso_totale == pytest.approx(0.40)


def test_intermediazione_calcolata_sul_valore_del_file_non_sullo_scontato(ipotesi):
    """Cambiando il FAB l'intermediazione non cambia: dipende solo dal valore del file."""
    uno = valutazione.calcola(immobile(fab=1, prezzo_base=500_000), ipotesi, 12)
    dieci = valutazione.calcola(immobile(fab=10, prezzo_base=500_000), ipotesi, 12)
    assert uno.intermediazione == pytest.approx(dieci.intermediazione) == pytest.approx(50_000)
    assert uno.prezzo_acquisto < dieci.prezzo_acquisto


def test_intermediazione_entra_nella_cassa_iniziale(ipotesi):
    p = valutazione.calcola(immobile(prezzo_base=200_000), ipotesi, 12)
    assert p.intermediazione > 0
    assert p.totale_costi_acquisto > p.intermediazione
    assert p.cassa_iniziale == pytest.approx(
        p.prezzo_acquisto + p.totale_costi_acquisto + p.capex_ristrutturazione
    )


def test_intermediazione_azzerabile(ipotesi):
    ipotesi["acquisto"]["intermediazione_pct"] = 0.0
    p = valutazione.calcola(immobile(prezzo_base=200_000), ipotesi, 12)
    assert p.intermediazione == 0
    assert p.percentuale_esborso_totale == pytest.approx(p.percentuale_acquisto)


# ------------------------------------------------- rivendita sul valore file

def test_rivendita_e_il_valore_del_file_meno_lo_sconto(ipotesi):
    """200.000 EUR nel file, sconto del 30% => si rivende a 140.000 EUR."""
    p = valutazione.calcola(immobile(prezzo_base=200_000), ipotesi, 12)
    assert p.metodo_uscita == "file"
    assert p.prezzo_uscita == pytest.approx(140_000)
    assert p.prezzo_uscita_da_file == pytest.approx(140_000)


def test_le_due_letture_restano_entrambe_visibili(ipotesi):
    p = valutazione.calcola(immobile(prezzo_base=200_000), ipotesi, 12)
    assert p.prezzo_uscita_da_file > 0
    assert p.prezzo_uscita_da_mercato > 0
    assert p.prezzo_uscita_da_file != p.prezzo_uscita_da_mercato


def test_metodo_mercato_usa_i_comparabili(ipotesi):
    ipotesi["uscita"]["metodo"] = "mercato"
    p = valutazione.calcola(immobile(prezzo_base=200_000), ipotesi, 12)
    assert p.metodo_uscita == "mercato"
    assert p.prezzo_uscita == pytest.approx(p.prezzo_uscita_da_mercato)


def test_metodo_prudenziale_prende_il_minore(ipotesi):
    ipotesi["uscita"]["metodo"] = "prudenziale"
    p = valutazione.calcola(immobile(prezzo_base=200_000), ipotesi, 12)
    assert p.prezzo_uscita == pytest.approx(
        min(p.prezzo_uscita_da_file, p.prezzo_uscita_da_mercato)
    )


def test_sconto_di_rivendita_configurabile(ipotesi):
    ipotesi["uscita"]["sconto_su_valore_file_pct"] = 0.20
    p = valutazione.calcola(immobile(prezzo_base=200_000), ipotesi, 12)
    assert p.prezzo_uscita == pytest.approx(160_000)


def test_divario_fra_le_due_letture_viene_segnalato(ipotesi):
    """Un immobile grande in zona di pregio: i comparabili superano di molto la regola."""
    p = valutazione.calcola(
        immobile(prezzo_base=100_000, superficie_mq=300, comune="Milano", provincia="MI"),
        ipotesi, 12,
    )
    assert any("comparabili di zona" in w for w in p.warning)


def test_esborso_totale_e_rivendita_determinano_il_margine(ipotesi):
    """Con esborso al 40% e rivendita al 70% il margine lordo e' il 30% del valore file."""
    valore = 200_000.0
    p = valutazione.calcola(immobile(prezzo_base=valore, superficie_mq=100), ipotesi, 12)
    margine_lordo = p.prezzo_uscita - (p.prezzo_acquisto + p.intermediazione)
    assert margine_lordo == pytest.approx(valore * 0.30)
    # I costi accessori e la gestione erodono quel margine
    assert p.utile < margine_lordo
