"""Costi di acquisto, imposte e oneri di mantenimento calibrati per zona."""
from __future__ import annotations

from app import config
from app.models import Immobile

# Fasce di rendita catastale stimata: la fascia A copre le grandi citta'
_FASCE_RENDITA = ("fascia_A", "fascia_B", "fascia_C")

# Tipologie del portafoglio -> chiave usata nei dataset dei costi
_CHIAVE_COSTI = {
    "residenziale": "residenziale", "ufficio": "ufficio", "ricettivo": "ricettivo",
    "capannone": "capannone", "commerciale": "commerciale", "box": "box",
    "terreno": "terreno", "altro": "residenziale",
}


def _chiave(imm: Immobile) -> str:
    return _CHIAVE_COSTI.get(imm.tipologia, "residenziale")


# --------------------------------------------------------------------------
# Notaio e imposte di acquisto
# --------------------------------------------------------------------------

def notaio(prezzo: float, ipotesi: dict) -> float:
    """Onorario notarile per scaglioni + IVA + spese accessorie."""
    acq = ipotesi["acquisto"]
    onorario = None
    for soglia, importo in acq["notaio_scaglioni"]:
        if prezzo <= soglia:
            onorario = float(importo)
            break
    if onorario is None:
        ultima_soglia, ultimo_importo = acq["notaio_scaglioni"][-1]
        onorario = float(ultimo_importo) + (prezzo - ultima_soglia) * acq["notaio_pct_oltre_ultimo_scaglione"]
    return onorario * (1 + acq["notaio_iva_pct"]) + acq["notaio_spese_accessorie"]


def costi_acquisto(prezzo_acquisto: float, ipotesi: dict) -> dict[str, float]:
    """Imposta di registro (acquisto da fondo), imposte fisse, notaio, agenzia, due diligence."""
    acq = ipotesi["acquisto"]
    registro = max(prezzo_acquisto * acq["imposta_registro_pct"], acq["imposta_registro_minima"])
    fisse = acq["imposta_ipotecaria_fissa"] + acq["imposta_catastale_fissa"]
    parcella_notaio = notaio(prezzo_acquisto, ipotesi)
    agenzia = max(
        prezzo_acquisto * acq["commissione_agenzia_acquisto_pct"],
        acq["commissione_agenzia_acquisto_minima"],
    )
    altri = acq["due_diligence_fissa"] + acq["perizia_fissa"] + acq["visure_volture_fissa"]
    return {
        "imposta_registro": registro,
        "imposte_fisse": fisse,
        "notaio": parcella_notaio,
        "commissione_acquisto": agenzia,
        "altri_costi_acquisto": altri,
        "totale": registro + fisse + parcella_notaio + agenzia + altri,
    }


# --------------------------------------------------------------------------
# IMU
# --------------------------------------------------------------------------

def _aliquota(imm: Immobile) -> float:
    dati = config.imu_oneri()
    comune = (imm.comune or "").strip().upper()
    if comune in dati["aliquote_comuni"]:
        return float(dati["aliquote_comuni"][comune])
    per_regione = dati["aliquote_default_per_regione"]
    return float(per_regione.get(imm.regione, per_regione["_default"]))


def _moltiplicatore_catastale(categoria: str, tipologia: str) -> float:
    molt = config.imu_oneri()["moltiplicatori_catastali"]
    cat = (categoria or "").strip().upper().replace(" ", "")
    if cat in molt:
        return float(molt[cat])
    if cat.startswith("A/10"):
        return float(molt["A/10"])
    if cat.startswith("D/5"):
        return float(molt["D/5"])
    if cat[:1] in {"A", "B", "C", "D"}:
        prefisso = cat[:3] if cat[:1] == "C" and len(cat) >= 3 else cat[:1]
        if prefisso in molt:
            return float(molt[prefisso])
        return float(molt.get(cat[:1], 160))
    predefiniti = {"ufficio": 80.0, "capannone": 65.0, "commerciale": 55.0, "box": 160.0}
    return predefiniti.get(tipologia, 160.0)


def _fascia_rendita(comune: str) -> str:
    tabella = config.imu_oneri()["rendita_stimata_eur_mq"]
    c = (comune or "").strip().upper()
    for fascia in _FASCE_RENDITA[:-1]:
        if c in tabella[fascia]["_comuni"]:
            return fascia
    return "fascia_C"


def imu_annua(imm: Immobile, valore_mercato: float = 0.0) -> tuple[float, str, dict]:
    """IMU annua. Ritorna (importo, metodo usato, dettaglio del calcolo).

    Usa la rendita catastale reale se presente nel file: e' il metodo esatto.
    Altrimenti stima la rendita dalla superficie con i parametri della zona.
    """
    dati = config.imu_oneri()
    aliquota = _aliquota(imm)

    if imm.e_terreno:
        terreni = dati["imu_terreni"]
        mq = imm.superficie_mq or 0.0
        if imm.destinazione_terreno == "edificabile":
            base = valore_mercato or 0.0
            importo = base * terreni["aliquota_edificabile"]
            metodo = "terreno edificabile: aliquota su valore venale"
            dettaglio = {"base_imponibile": base, "aliquota": terreni["aliquota_edificabile"]}
        else:
            reddito = mq * terreni["reddito_dominicale_stimato_eur_mq"]
            base = reddito * dati["rivalutazione_reddito_dominicale"] * dati["moltiplicatori_catastali"]["terreno_agricolo"]
            importo = base * terreni["aliquota_agricolo"]
            metodo = "terreno agricolo: reddito dominicale stimato (esente per CD/IAP e comuni montani)"
            dettaglio = {"reddito_dominicale": reddito, "base_imponibile": base,
                         "aliquota": terreni["aliquota_agricolo"]}
        return importo, metodo, dettaglio

    moltiplicatore = _moltiplicatore_catastale(imm.categoria_catastale, imm.tipologia)

    if imm.rendita_catastale and imm.rendita_catastale > 0:
        rendita = float(imm.rendita_catastale)
        metodo = "rendita catastale da file (calcolo esatto)"
    else:
        fascia = _fascia_rendita(imm.comune)
        tabella = dati["rendita_stimata_eur_mq"][fascia]
        eur_mq = float(tabella.get(_chiave(imm), tabella["residenziale"]))
        mq = imm.superficie_mq or 0.0
        rendita = mq * eur_mq
        metodo = f"rendita stimata ({fascia.replace('_', ' ')}, {eur_mq:.0f} EUR/mq)"

    base = rendita * dati["rivalutazione_rendita"] * moltiplicatore
    return base * aliquota, metodo, {
        "rendita": rendita,
        "rivalutazione": dati["rivalutazione_rendita"],
        "moltiplicatore": moltiplicatore,
        "base_imponibile": base,
        "aliquota": aliquota,
    }


# --------------------------------------------------------------------------
# Oneri ricorrenti
# --------------------------------------------------------------------------

def oneri_annui(imm: Immobile, ipotesi: dict) -> dict[str, float]:
    """Condominio, TARI, assicurazione, manutenzione, utenze - calibrati per regione."""
    dati = config.imu_oneri()
    voci = dati["oneri_gestione_eur_mq_anno"].get(
        _chiave(imm), dati["oneri_gestione_eur_mq_anno"]["residenziale"]
    )
    molt_regione = dati["moltiplicatore_oneri_per_regione"]
    fattore = float(molt_regione.get(imm.regione, molt_regione["_default"]))
    mq = imm.superficie_mq or 0.0
    occupato = imm.stato_occupazione in {"occupato", "parzialmente_occupato", "occupato_senza_titolo"}

    dettaglio: dict[str, float] = {}
    for voce, eur_mq in voci.items():
        if voce.startswith("_"):
            continue
        importo = mq * float(eur_mq) * fattore
        if voce == "tari" and not occupato and not ipotesi["mantenimento"]["applica_tari_se_libero"]:
            importo = 0.0
        if voce == "utenze_vuoto" and occupato:
            importo = 0.0  # a carico del conduttore
        dettaglio[voce] = importo
    return dettaglio


def capex_ristrutturazione(imm: Immobile) -> float:
    tabella = config.imu_oneri()["costo_ristrutturazione_eur_mq"]
    per_tipo = tabella.get(_chiave(imm), tabella["residenziale"])
    stato = imm.stato_conservazione if imm.stato_conservazione != "sconosciuto" else "buono"
    return (imm.superficie_mq or 0.0) * float(per_tipo.get(stato, 0.0))
