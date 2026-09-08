"""Collegamenti cartografici e catastali per ogni immobile."""
from __future__ import annotations

from urllib.parse import quote_plus

from app.models import Immobile


def _query(imm: Immobile) -> str:
    indirizzo = imm.indirizzo_completo()
    return indirizzo if indirizzo else (imm.comune or imm.provincia or "Italia")


def link(imm: Immobile) -> dict[str, str]:
    """URL pronti per i pulsanti della scheda immobile.

    Con le coordinate puntiamo esattamente sul punto; senza, cerchiamo l'indirizzo.
    """
    q = quote_plus(_query(imm) + ", Italia")
    ha_coordinate = imm.lat is not None and imm.lng is not None

    if ha_coordinate:
        coord = f"{imm.lat},{imm.lng}"
        maps = f"https://www.google.com/maps/search/?api=1&query={coord}"
        earth = f"https://earth.google.com/web/@{imm.lat},{imm.lng},0a,600d,35y,0h,45t,0r"
        satellite = f"https://www.google.com/maps/@?api=1&map_action=map&center={coord}&zoom=18&basemap=satellite"
        street = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={coord}"
    else:
        maps = f"https://www.google.com/maps/search/?api=1&query={q}"
        earth = f"https://earth.google.com/web/search/{q}"
        satellite = maps + "&basemap=satellite"
        street = f"https://www.google.com/maps/search/?api=1&query={q}&layer=c"

    return {
        "google_maps": maps,
        "google_earth": earth,
        "satellite": satellite,
        "street_view": street,
        "openstreetmap": (
            f"https://www.openstreetmap.org/?mlat={imm.lat}&mlon={imm.lng}#map=18/{imm.lat}/{imm.lng}"
            if ha_coordinate else f"https://www.openstreetmap.org/search?query={q}"
        ),
        "catasto": "https://sister.agenziaentrate.gov.it/CitizenServices/",
        "quotazioni_omi": "https://www1.agenziaentrate.gov.it/servizi/Consultazione/ricerca.htm",
        "ha_coordinate": "si" if ha_coordinate else "no",
    }
