"""Riconoscimento automatico delle colonne e normalizzazione dei valori.

I file dei fondi non hanno uno schema comune: ogni pool usa intestazioni diverse
("Prezzo base", "Valore di perizia", "Sup. commerciale", "Stato occupativo"...).
Qui mappiamo qualunque intestazione sullo schema canonico di ``Immobile``.
"""
from __future__ import annotations

import re
import unicodedata

from app import config

# --------------------------------------------------------------------------
# Normalizzazione testo
# --------------------------------------------------------------------------

def slug(testo: object) -> str:
    """Riduce un'intestazione a una forma confrontabile: minuscolo, senza accenti."""
    if testo is None:
        return ""
    s = unicodedata.normalize("NFKD", str(testo))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("'", " ").replace("`", " ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------
# Sinonimi per campo canonico (ordine = priorita')
# --------------------------------------------------------------------------

SINONIMI: dict[str, list[str]] = {
    "lotto": ["lotto", "n lotto", "numero lotto", "id lotto", "codice lotto", "asset id",
              "id immobile", "codice immobile", "cod immobile", "riferimento", "rif", "id"],
    "fab_raw": ["fab", "fabbricato", "cod fab", "codice fab", "classe fab", "categoria fab",
                "fascia", "classe"],
    "tipologia": ["tipologia", "tipo immobile", "tipo", "destinazione uso", "destinazione d uso",
                  "destinazione", "categoria immobile", "asset class", "uso", "natura"],
    "indirizzo": ["indirizzo", "via", "ubicazione", "localita", "indirizzo immobile",
                  "toponimo", "via piazza", "posizione"],
    "comune": ["comune", "citta", "municipio", "comune ubicazione", "town", "city"],
    "provincia": ["provincia", "prov", "sigla provincia", "pv", "prov sigla"],
    "regione": ["regione", "region"],
    "cap": ["cap", "codice avviamento postale", "zip"],
    "lat": ["lat", "latitudine", "latitude"],
    "lng": ["lng", "lon", "long", "longitudine", "longitude"],
    "superficie_mq": ["superficie commerciale", "sup commerciale", "superficie mq", "mq",
                      "metri quadri", "metri quadrati", "superficie", "sup", "sup lorda",
                      "superficie lorda", "consistenza mq", "superficie catastale", "smq",
                      "superficie utile", "sup netta", "sup mq"],
    "vani": ["vani", "numero vani", "n vani", "locali", "numero locali"],
    "piano": ["piano", "livello", "piano immobile"],
    "categoria_catastale": ["categoria catastale", "cat catastale", "categoria", "cat cat",
                            "classamento", "cat"],
    "foglio": ["foglio", "fg", "foglio catastale"],
    "particella": ["particella", "part", "mappale", "map", "particella catastale", "pll"],
    "subalterno": ["subalterno", "sub", "sub catastale"],
    "rendita_catastale": ["rendita catastale", "rendita", "rc", "rendita cat"],
    "stato_occupazione": ["stato occupazione", "stato occupativo", "occupazione", "occupato",
                          "stato locativo", "locazione", "situazione occupativa", "libero occupato",
                          "stato di occupazione", "occupancy"],
    "stato_conservazione": ["stato conservazione", "stato manutentivo", "stato immobile",
                            "condizioni", "stato", "manutenzione", "stato di conservazione",
                            "conservazione", "condizione"],
    "canone_annuo": ["canone annuo", "canone", "canone locazione", "affitto annuo",
                     "reddito annuo", "canone annuale", "rent"],
    "destinazione_terreno": ["destinazione urbanistica", "destinazione terreno", "urbanistica",
                             "zona urbanistica", "edificabilita"],
    "indice_edificabilita": ["indice edificabilita", "indice di edificabilita", "if", "indice fondiario",
                             "indice territoriale", "mc mq", "mq mq", "indice"],
    "prezzo_base": ["prezzo base", "base d asta", "prezzo base asta", "valore base",
                    "prezzo di vendita", "prezzo", "valore", "importo", "valore immobile",
                    "prezzo richiesto", "asking price", "valore di libro", "book value",
                    "valore contabile", "prezzo minimo", "offerta minima"],
    "prezzo_perizia": ["valore perizia", "perizia", "valore di perizia", "stima peritale",
                       "valore stimato", "omv", "market value", "valore di mercato"],
    "note": ["note", "annotazioni", "descrizione", "commento", "osservazioni", "dettagli"],
}

# Campi in cui cercare un "FAB n" se non esiste una colonna dedicata
CAMPI_TESTUALI_PER_FAB = ("lotto", "note", "tipologia", "indirizzo", "fab_raw")

_RE_FAB = re.compile(r"\bfab(?:bricato)?\s*[-_.:n°#]*\s*(\d{1,2})\b", re.IGNORECASE)


def rileva_colonne(intestazioni: list[str]) -> dict[str, str]:
    """Associa ogni campo canonico all'intestazione piu' plausibile.

    Match esatto sullo slug, poi match per contenimento. Ogni colonna sorgente
    viene assegnata a un solo campo per evitare che 'superficie' rubi 'superficie
    commerciale'.
    """
    slugs = {h: slug(h) for h in intestazioni}
    mappa: dict[str, str] = {}
    usate: set[str] = set()

    for campo, alias in SINONIMI.items():
        for a in alias:
            trovata = next(
                (h for h, s in slugs.items() if s == a and h not in usate), None
            )
            if trovata:
                mappa[campo] = trovata
                usate.add(trovata)
                break
        if campo in mappa:
            continue
        for a in alias:
            trovata = next(
                (h for h, s in slugs.items()
                 if s and h not in usate and (a in s or s in a) and abs(len(s) - len(a)) <= 12),
                None,
            )
            if trovata:
                mappa[campo] = trovata
                usate.add(trovata)
                break
    return mappa


# --------------------------------------------------------------------------
# Parser di valore
# --------------------------------------------------------------------------

def numero(valore: object) -> float | None:
    """Converte '€ 1.250.000,50', '1,250,000.50', '250 mq' in float."""
    if valore is None:
        return None
    if isinstance(valore, (int, float)) and not isinstance(valore, bool):
        v = float(valore)
        return None if v != v else v  # scarta NaN
    testo = str(valore).strip()
    if not testo or slug(testo) in {"na", "n a", "nd", "n d", "", "-", "non disponibile"}:
        return None
    testo = re.sub(r"[^\d,.\-]", "", testo)
    if not testo or testo in {"-", ".", ","}:
        return None

    ha_virgola, ha_punto = "," in testo, "." in testo
    if ha_virgola and ha_punto:
        # L'ultimo separatore che compare e' quello decimale
        if testo.rfind(",") > testo.rfind("."):
            testo = testo.replace(".", "").replace(",", ".")
        else:
            testo = testo.replace(",", "")
    elif ha_virgola:
        # ',' decimale se seguito da 1-2 cifre finali, altrimenti separatore migliaia
        testo = testo.replace(",", "." if re.search(r",\d{1,2}$", testo) else "")
    elif ha_punto:
        if re.search(r"\.\d{3}(\.\d{3})*$", testo):
            testo = testo.replace(".", "")
    try:
        return float(testo)
    except ValueError:
        return None


def estrai_fab(*valori: object) -> tuple[int | None, str]:
    """Cerca 'FAB 3' / 'FAB-07' nei valori passati; accetta anche un numero secco."""
    for v in valori:
        if v is None:
            continue
        testo = str(v).strip()
        if not testo:
            continue
        m = _RE_FAB.search(testo)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 10:
                return n, testo
        if re.fullmatch(r"\d{1,2}([.,]0+)?", testo):
            n = int(float(testo.replace(",", ".")))
            if 1 <= n <= 10:
                return n, testo
    return None, ""


_TIPOLOGIA_REGOLE: list[tuple[str, tuple[str, ...]]] = [
    ("terreno", ("terreno", "terreni", "fondo agricolo", "area edificabile", "lotto di terreno",
                 "seminativo", "agricolo", "area fabbricabile", "appezzamento")),
    ("ricettivo", ("ricettiv", "albergo", "hotel", "b b", "bed and breakfast", "agriturismo",
                   "residence", "affittacamere", "turistic", "resort", "ostello")),
    ("capannone", ("capannone", "industriale", "opificio", "laboratorio", "magazzino",
                   "deposito", "logistic", "artigianal", "stabilimento")),
    ("ufficio", ("ufficio", "uffici", "studio", "direzional", "office", "a 10")),
    ("commerciale", ("negozio", "commercial", "bottega", "locale commerciale", "retail",
                     "esercizio", "c 1")),
    ("box", ("box", "garage", "autorimessa", "posto auto", "cantina", "c 6")),
    ("residenziale", ("residenzial", "appartamento", "abitazione", "casa", "villa", "villetta",
                      "immobile residenziale", "civile abitazione", "monolocale", "bilocale",
                      "trilocale", "attico", "mansarda", "a 2", "a 3", "a 4", "a 7")),
]


def classifica_tipologia(*valori: object) -> str:
    testo = " ".join(slug(v) for v in valori if v not in (None, ""))
    if not testo:
        return "altro"
    for tipo, chiavi in _TIPOLOGIA_REGOLE:
        if any(k in testo for k in chiavi):
            return tipo
    return "altro"


def classifica_occupazione(*valori: object) -> str:
    testo = " ".join(slug(v) for v in valori if v not in (None, ""))
    if not testo:
        return "sconosciuto"
    if any(k in testo for k in ("senza titolo", "abusiv", "occupazione illegittima", "sine titulo")):
        return "occupato_senza_titolo"
    if any(k in testo for k in ("parzialmente occupato", "parz occupato", "in parte occupato")):
        return "parzialmente_occupato"
    if any(k in testo for k in ("libero", "sfitto", "vuoto", "non occupato", "disponibile", "free")):
        return "libero"
    if any(k in testo for k in ("occupato", "locato", "affittato", "in locazione", "condotto",
                                "con inquilino", "leased", "occupied", "si")):
        return "occupato"
    return "sconosciuto"


def classifica_conservazione(*valori: object) -> str:
    testo = " ".join(slug(v) for v in valori if v not in (None, ""))
    if not testo:
        return "sconosciuto"
    if any(k in testo for k in ("da demolire", "rudere", "diroccato", "collabente", "grezzo",
                                "al grezzo", "scheletro")):
        return "grezzo"
    if any(k in testo for k in ("ristrutturazione totale", "da ristrutturare totalmente",
                                "totalmente da ristrutturare", "pessimo", "fatiscente",
                                "ristrutturazione integrale")):
        return "da_ristrutturare_totale"
    if any(k in testo for k in ("da ristrutturare", "da rifare", "da sistemare", "da riqualificare",
                                "scadente", "mediocre", "da manutenere", "necessita interventi")):
        return "da_ristrutturare"
    if any(k in testo for k in ("nuovo", "nuova costruzione", "ristrutturato", "recente",
                                "appena ristrutturato", "ottimo")):
        return "nuovo"
    if any(k in testo for k in ("sano", "buono", "buone condizioni", "abitabile", "discreto",
                                "normale", "in ordine", "ok")):
        return "buono"
    return "sconosciuto"


def classifica_destinazione_terreno(*valori: object) -> str:
    testo = " ".join(slug(v) for v in valori if v not in (None, ""))
    if not testo:
        return "sconosciuto"
    if any(k in testo for k in ("industrial", "artigianal", "produttiv", "d1", "d 1")):
        return "industriale"
    if any(k in testo for k in ("edificabil", "fabbricabil", "residenzial", "urbanizzat",
                                "lottizzat", "zona b", "zona c")):
        return "edificabile"
    if any(k in testo for k in ("agricol", "seminativ", "boschiv", "pascolo", "vigneto",
                                "uliveto", "frutteto", "zona e")):
        return "agricolo"
    return "sconosciuto"


# --------------------------------------------------------------------------
# Geografia
# --------------------------------------------------------------------------

_COMUNI_NOTI = {
    "MILANO": "MI", "ROMA": "RM", "TORINO": "TO", "NAPOLI": "NA", "PALERMO": "PA",
    "GENOVA": "GE", "BOLOGNA": "BO", "FIRENZE": "FI", "BARI": "BA", "CATANIA": "CT",
    "VENEZIA": "VE", "VERONA": "VR", "MESSINA": "ME", "PADOVA": "PD", "TRIESTE": "TS",
    "BRESCIA": "BS", "PARMA": "PR", "PRATO": "PO", "MODENA": "MO", "REGGIO CALABRIA": "RC",
    "REGGIO EMILIA": "RE", "PERUGIA": "PG", "RAVENNA": "RA", "LIVORNO": "LI", "RIMINI": "RN",
    "CAGLIARI": "CA", "FOGGIA": "FG", "FERRARA": "FE", "SALERNO": "SA", "LATINA": "LT",
    "GIUGLIANO IN CAMPANIA": "NA", "MONZA": "MB", "SIRACUSA": "SR", "PESCARA": "PE",
    "BERGAMO": "BG", "FORLI": "FC", "TRENTO": "TN", "VICENZA": "VI", "TERNI": "TR",
    "BOLZANO": "BZ", "NOVARA": "NO", "PIACENZA": "PC", "ANCONA": "AN", "ANDRIA": "BT",
    "AREZZO": "AR", "UDINE": "UD", "CESENA": "FC", "LECCE": "LE", "PESARO": "PU",
    "BARLETTA": "BT", "ALESSANDRIA": "AL", "PISA": "PI", "COMO": "CO", "LUCCA": "LU",
    "BRINDISI": "BR", "TORRE DEL GRECO": "NA", "TREVISO": "TV", "BUSTO ARSIZIO": "VA",
    "COSENZA": "CS", "MARSALA": "TP", "GRosseto": "GR", "SESTO SAN GIOVANNI": "MI",
    "VARESE": "VA", "ASTI": "AT", "CINISELLO BALSAMO": "MI", "GELA": "CL", "APRILIA": "LT",
    "RAGUSA": "RG", "PAVIA": "PV", "CREMONA": "CR", "CARPI": "MO", "QUARTU SANT ELENA": "CA",
    "LAMEZIA TERME": "CZ", "ALTAMURA": "BA", "IMOLA": "BO", "L AQUILA": "AQ", "MASSA": "MS",
    "TRAPANI": "TP", "VITERBO": "VT", "COSENZA ": "CS", "POTENZA": "PZ", "CASERTA": "CE",
    "CATANZARO": "CZ", "MATERA": "MT", "SASSARI": "SS", "SIENA": "SI", "MANTOVA": "MN",
    "LECCO": "LC", "SONDRIO": "SO", "LODI": "LO", "BIELLA": "BI", "VERCELLI": "VC",
    "CUNEO": "CN", "SAVONA": "SV", "IMPERIA": "IM", "LA SPEZIA": "SP", "AOSTA": "AO",
    "CAMPOBASSO": "CB", "ISERNIA": "IS", "ENNA": "EN", "CALTANISSETTA": "CL",
    "AGRIGENTO": "AG", "NUORO": "NU", "ORISTANO": "OR", "TARANTO": "TA", "CHIETI": "CH",
    "TERAMO": "TE", "MACERATA": "MC", "FERMO": "FM", "ASCOLI PICENO": "AP", "RIETI": "RI",
    "FROSINONE": "FR", "BENEVENTO": "BN", "AVELLINO": "AV", "CROTONE": "KR",
    "VIBO VALENTIA": "VV", "PISTOIA": "PT", "GORIZIA": "GO", "PORDENONE": "PN",
    "BELLUNO": "BL", "ROVIGO": "RO", "VERBANIA": "VB",
}


def risolvi_geografia(comune: str, provincia: str, regione: str) -> tuple[str, str, str]:
    """Restituisce (comune, sigla_provincia, regione) completando il mancante."""
    province = config.geografia()["province"]
    comune = (comune or "").strip()
    sigla = (provincia or "").strip().upper()

    if sigla and sigla not in province:
        # E' stato scritto il nome esteso della provincia, non la sigla
        atteso = slug(sigla)
        trovato = next((s for s, (nome, _) in province.items() if slug(nome) == atteso), "")
        if not trovato:
            trovato = next(
                (s for s, (nome, _) in province.items() if atteso and atteso in slug(nome)), ""
            )
        sigla = trovato

    if not sigla and comune:
        sigla = _COMUNI_NOTI.get(slug(comune).upper(), "")
        if not sigla:
            sigla = next(
                (s for s, (nome, _) in province.items() if slug(nome) == slug(comune)), ""
            )

    reg = (regione or "").strip()
    if sigla in province:
        if not comune:
            comune = province[sigla][0]
        reg = province[sigla][1]
    return comune, sigla, reg
