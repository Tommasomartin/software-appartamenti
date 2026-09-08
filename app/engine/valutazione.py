"""Prospetto economico completo: dall'acquisto scontato all'incasso netto di rivendita."""
from __future__ import annotations

from app import config
from app.engine import comparabili, costi
from app.engine.punteggio import assegna_semaforo, calcola_confidenza
from app.models import Immobile, Prospetto


def euro_it(valore: float) -> str:
    """Formatta un importo in stile italiano per i messaggi di avviso."""
    return f"{valore:,.0f} EUR".replace(",", ".")


def percentuale_acquisto(imm: Immobile, ipotesi: dict) -> float:
    """Quota del prezzo a base d'asta effettivamente pagata, secondo il FAB.

    FAB basso = piu' sconto (paghiamo meno). FAB alto = meno sconto.
    """
    scala = ipotesi["fab"]["scala"]
    if imm.fab is not None and str(imm.fab) in scala:
        return float(scala[str(imm.fab)])
    return float(ipotesi["fab"]["percentuale_se_fab_assente"])


def _piano_categoria(piano: str) -> str:
    p = (piano or "").strip().lower()
    if not p:
        return "intermedio"
    if any(k in p for k in ("attico", "penthouse")):
        return "attico"
    if any(k in p for k in ("seminterrato", "interrato", "s1", "-1")):
        return "seminterrato"
    if any(k in p for k in ("terra", "t", "pt", "rialzato")) and len(p) <= 8:
        return "terra"
    if "ultimo" in p:
        return "ultimo"
    return "intermedio"


def _superficie_valorizzabile(imm: Immobile) -> float:
    return float(imm.superficie_mq or 0.0)


def calcola(imm: Immobile, ipotesi: dict, orizzonte_mesi: int | None = None) -> Prospetto:
    mkt = config.mercato()
    rettifiche = mkt["coefficienti_rettifica"]
    mesi = int(orizzonte_mesi or ipotesi.get("orizzonte_mesi", 12))
    p = Prospetto(immobile_id=imm.id, orizzonte_mesi=mesi)

    # ---------------- Acquisto ----------------
    prezzo_base = float(imm.prezzo_base or 0.0)
    p.percentuale_acquisto = percentuale_acquisto(imm, ipotesi)
    p.prezzo_acquisto = prezzo_base * p.percentuale_acquisto

    voci_acquisto = costi.costi_acquisto(p.prezzo_acquisto, ipotesi, prezzo_base)
    p.intermediazione = voci_acquisto["intermediazione"]
    p.imposta_registro = voci_acquisto["imposta_registro"]
    p.imposte_fisse = voci_acquisto["imposte_fisse"]
    p.notaio = voci_acquisto["notaio"]
    p.commissione_acquisto = voci_acquisto["commissione_acquisto"]
    p.altri_costi_acquisto = voci_acquisto["altri_costi_acquisto"]
    p.totale_costi_acquisto = voci_acquisto["totale"]
    p.capex_ristrutturazione = costi.capex_ristrutturazione(imm)
    p.cassa_iniziale = p.prezzo_acquisto + p.totale_costi_acquisto + p.capex_ristrutturazione
    if prezzo_base > 0:
        # Quota del valore a base d'asta che esce di cassa fra prezzo e intermediazione
        p.percentuale_esborso_totale = (p.prezzo_acquisto + p.intermediazione) / prezzo_base

    # ---------------- Valore di mercato e uscita ----------------
    comp = comparabili.stima(imm)
    p.comparabili = comp.to_dict()
    p.valore_mercato_eur_mq = comp.eur_mq

    mq = _superficie_valorizzabile(imm)
    valore_lordo = comp.eur_mq * mq
    if valore_lordo <= 0:
        # Senza superficie ripieghiamo sul valore dichiarato nel file
        valore_lordo = float(imm.prezzo_perizia or prezzo_base)
        p.warning.append("Superficie assente: valore di uscita stimato sul dato del file, non sui mq.")

    coefficienti: dict[str, float] = {}
    if imm.e_terreno:
        coefficienti["stato_occupazione"] = rettifiche["stato_occupazione"].get(
            imm.stato_occupazione, 1.0
        )
        coefficienti["liquidita_tipologia"] = rettifiche["liquidita_tipologia"]["terreno"]
    else:
        coefficienti["stato_conservazione"] = rettifiche["stato_conservazione"].get(
            imm.stato_conservazione, 1.0
        )
        coefficienti["stato_occupazione"] = rettifiche["stato_occupazione"].get(
            imm.stato_occupazione, 1.0
        )
        coefficienti["piano"] = rettifiche["piano"][_piano_categoria(imm.piano)]
        coefficienti["liquidita_tipologia"] = rettifiche["liquidita_tipologia"].get(
            imm.tipologia, rettifiche["liquidita_tipologia"]["altro"]
        )

    # La ristrutturazione e' gia' a costo: se la eseguiamo, l'immobile esce come "buono"
    if p.capex_ristrutturazione > 0 and not imm.e_terreno:
        coefficienti["stato_conservazione"] = rettifiche["stato_conservazione"]["buono"]
        coefficienti["_nota_capex"] = 1.0

    fattore = 1.0
    for chiave, valore in coefficienti.items():
        if not chiave.startswith("_"):
            fattore *= float(valore)

    usc = ipotesi["uscita"]
    coefficienti["sconto_trattativa"] = 1 - usc["sconto_trattativa_pct"]
    p.coefficienti_applicati = {k: round(float(v), 4) for k, v in coefficienti.items()}
    p.valore_mercato_lordo = valore_lordo

    # Due letture indipendenti del prezzo di rivendita, tenute entrambe visibili.
    # 1) Regola commerciale: si rivende a uno sconto fisso sul valore scritto nel file.
    # 2) Stima di mercato: comparabili al mq rettificati per le caratteristiche.
    p.prezzo_uscita_da_file = prezzo_base * (1 - usc["sconto_su_valore_file_pct"])
    if usc.get("applica_rettifiche_al_metodo_file"):
        # Opzionale: anche la regola commerciale sconta occupazione e stato di fatto
        p.prezzo_uscita_da_file *= fattore
    p.prezzo_uscita_da_mercato = valore_lordo * fattore * (1 - usc["sconto_trattativa_pct"])

    metodo = usc.get("metodo", "file")
    if metodo == "mercato" or p.prezzo_uscita_da_file <= 0:
        p.prezzo_uscita = p.prezzo_uscita_da_mercato
        p.metodo_uscita = "mercato"
    elif metodo == "prudenziale":
        p.prezzo_uscita = min(p.prezzo_uscita_da_file, p.prezzo_uscita_da_mercato)
        p.metodo_uscita = "prudenziale"
    else:
        p.prezzo_uscita = p.prezzo_uscita_da_file
        p.metodo_uscita = "file"

    p.commissione_vendita = p.prezzo_uscita * usc["commissione_agenzia_vendita_pct"]
    p.costi_uscita = usc["spese_marketing_fisse"] + usc["ape_e_pratiche_fisse"]

    # Le due letture devono essere dello stesso ordine di grandezza: se divergono
    # molto, o il valore del file e' fuori mercato o la stima a mq va verificata.
    if p.prezzo_uscita_da_file > 0 and p.prezzo_uscita_da_mercato > 0:
        divario = p.prezzo_uscita_da_mercato / p.prezzo_uscita_da_file
        if divario >= 1.6:
            p.warning.append(
                f"I comparabili di zona valgono {divario:.1f}x il prezzo di rivendita "
                f"da regola commerciale ({euro_it(p.prezzo_uscita_da_mercato)} contro "
                f"{euro_it(p.prezzo_uscita_da_file)}): potrebbe esserci piu' margine di quanto stimato."
            )
        elif divario <= 0.65:
            p.warning.append(
                f"I comparabili di zona valgono solo {divario:.0%} del prezzo di rivendita "
                f"da regola commerciale ({euro_it(p.prezzo_uscita_da_mercato)} contro "
                f"{euro_it(p.prezzo_uscita_da_file)}): il valore del file sembra fuori mercato."
            )
    for nota in comp.note:
        p.warning.append(nota)

    # ---------------- Mantenimento ----------------
    imu, metodo, _ = costi.imu_annua(imm, valore_mercato=p.valore_mercato_lordo)
    p.imu_annua = imu
    p.imu_metodo = metodo
    p.oneri_dettaglio = costi.oneri_annui(imm, ipotesi)
    p.oneri_annui = sum(p.oneri_dettaglio.values())

    man = ipotesi["mantenimento"]
    canone = float(imm.canone_annuo or 0.0)
    if canone <= 0 and imm.stato_occupazione == "occupato" and p.valore_mercato_lordo > 0:
        canone = p.valore_mercato_lordo * 0.035  # rendimento lordo prudenziale
        p.warning.append("Canone non indicato: ipotizzato un rendimento lordo del 3,5%.")
    if imm.stato_occupazione == "occupato_senza_titolo":
        canone = 0.0
    p.ricavo_locazione_annuo = canone * (1 - man["gestione_pct_su_canone"] - man["sfitto_pct_su_canone"])

    costo_capitale = p.cassa_iniziale * man["costo_capitale_annuo_pct"]
    p.mantenimento_netto_annuo = p.imu_annua + p.oneri_annui + costo_capitale - p.ricavo_locazione_annuo
    p.mantenimento_per_orizzonte = {
        f"m{m}": p.mantenimento_netto_annuo * m / 12 for m in man["orizzonti_mesi"]
    }
    p.mantenimento_per_orizzonte[f"m{mesi}"] = p.mantenimento_netto_annuo * mesi / 12
    mantenimento_periodo = p.mantenimento_netto_annuo * mesi / 12

    # ---------------- Sintesi ----------------
    p.investimento_totale = p.cassa_iniziale + mantenimento_periodo
    incasso = p.prezzo_uscita - p.commissione_vendita - p.costi_uscita

    if usc["applica_tassazione_plusvalenza"]:
        base_imponibile = max(0.0, incasso - p.cassa_iniziale)
        p.tassazione_plusvalenza = base_imponibile * usc["aliquota_plusvalenza_pct"]
        incasso -= p.tassazione_plusvalenza
    p.incasso_netto = incasso

    p.utile = p.incasso_netto - p.investimento_totale
    if p.investimento_totale > 0:
        p.multiplo = p.incasso_netto / p.investimento_totale
        p.roi = p.utile / p.investimento_totale
        anni = max(mesi / 12, 1 / 12)
        p.roi_annualizzato = (1 + p.roi) ** (1 / anni) - 1 if p.roi > -1 else -1.0
    if p.incasso_netto > 0:
        p.margine_su_ricavo = p.utile / p.incasso_netto

    # Prezzo di vendita minimo per andare a pareggio
    denominatore = 1 - usc["commissione_agenzia_vendita_pct"]
    if denominatore > 0:
        p.prezzo_pareggio = (p.investimento_totale + p.costi_uscita) / denominatore

    p.warning.extend(imm.warning_ingest)
    p.confidenza = calcola_confidenza(imm, comp)
    assegna_semaforo(p, imm, ipotesi)
    return p
