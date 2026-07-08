"""Geographic reference data for Czech towns.

Maps a town name to its administrative region (kraj) and provides an approximate
great-circle distance from Prague (km) via the haversine formula.

The table below is not exhaustive — it covers the statutory cities, all okres
(district) towns, and many mid-size towns that commonly run cultural houses,
festivals and Christmas markets. Unknown towns resolve via a normalized-name
lookup; if still unknown, ``region_for``/``km_from_prague`` return ``None`` and
the pipeline records the row with an empty region and a blank distance rather
than guessing.
"""

from __future__ import annotations

import math
import unicodedata
from functools import lru_cache
from typing import Optional, Tuple

PRAGUE_LAT, PRAGUE_LON = 50.0755, 14.4378

# name -> (region/kraj, latitude, longitude)
# Regions use the common short Czech names.
CITIES: dict[str, Tuple[str, float, float]] = {
    "Praha": ("Praha", 50.0755, 14.4378),
    "Brno": ("Jihomoravský", 49.1951, 16.6068),
    "Ostrava": ("Moravskoslezský", 49.8209, 18.2625),
    "Plzeň": ("Plzeňský", 49.7384, 13.3736),
    "Liberec": ("Liberecký", 50.7671, 15.0562),
    "Olomouc": ("Olomoucký", 49.5938, 17.2509),
    "České Budějovice": ("Jihočeský", 48.9745, 14.4743),
    "Hradec Králové": ("Královéhradecký", 50.2103, 15.8327),
    "Ústí nad Labem": ("Ústecký", 50.6607, 14.0323),
    "Pardubice": ("Pardubický", 50.0343, 15.7812),
    "Zlín": ("Zlínský", 49.2264, 17.6707),
    "Havířov": ("Moravskoslezský", 49.7799, 18.4369),
    "Kladno": ("Středočeský", 50.1477, 14.1028),
    "Most": ("Ústecký", 50.5030, 13.6362),
    "Opava": ("Moravskoslezský", 49.9387, 17.9026),
    "Frýdek-Místek": ("Moravskoslezský", 49.6835, 18.3506),
    "Karviná": ("Moravskoslezský", 49.8540, 18.5417),
    "Jihlava": ("Vysočina", 49.3961, 15.5912),
    "Teplice": ("Ústecký", 50.6404, 13.8245),
    "Děčín": ("Ústecký", 50.7821, 14.2148),
    "Karlovy Vary": ("Karlovarský", 50.2329, 12.8712),
    "Chomutov": ("Ústecký", 50.4605, 13.4177),
    "Jablonec nad Nisou": ("Liberecký", 50.7243, 15.1712),
    "Mladá Boleslav": ("Středočeský", 50.4114, 14.9030),
    "Prostějov": ("Olomoucký", 49.4720, 17.1118),
    "Přerov": ("Olomoucký", 49.4554, 17.4509),
    "Česká Lípa": ("Liberecký", 50.6855, 14.5378),
    "Třebíč": ("Vysočina", 49.2148, 15.8814),
    "Třinec": ("Moravskoslezský", 49.6776, 18.6708),
    "Tábor": ("Jihočeský", 49.4144, 14.6578),
    "Znojmo": ("Jihomoravský", 48.8555, 16.0488),
    "Příbram": ("Středočeský", 49.6899, 14.0104),
    "Cheb": ("Karlovarský", 50.0796, 12.3731),
    "Kolín": ("Středočeský", 50.0281, 15.2003),
    "Písek": ("Jihočeský", 49.3088, 14.1475),
    "Trutnov": ("Královéhradecký", 50.5608, 15.9127),
    "Kroměříž": ("Zlínský", 49.2979, 17.3931),
    "Šumperk": ("Olomoucký", 49.9653, 16.9706),
    "Vsetín": ("Zlínský", 49.3388, 17.9962),
    "Valašské Meziříčí": ("Zlínský", 49.4719, 17.9711),
    "Uherské Hradiště": ("Zlínský", 49.0697, 17.4597),
    "Břeclav": ("Jihomoravský", 48.7591, 16.8825),
    "Hodonín": ("Jihomoravský", 48.8489, 17.1327),
    "Český Těšín": ("Moravskoslezský", 49.7459, 18.6266),
    "Litoměřice": ("Ústecký", 50.5343, 14.1316),
    "Havlíčkův Brod": ("Vysočina", 49.6079, 15.5800),
    "Nový Jičín": ("Moravskoslezský", 49.5942, 18.0106),
    "Krnov": ("Moravskoslezský", 50.0894, 17.7040),
    "Sokolov": ("Karlovarský", 50.1814, 12.6404),
    "Hranice": ("Olomoucký", 49.5479, 17.7346),
    "Otrokovice": ("Zlínský", 49.2094, 17.5314),
    "Žďár nad Sázavou": ("Vysočina", 49.5626, 15.9396),
    "Blansko": ("Jihomoravský", 49.3636, 16.6444),
    "Klatovy": ("Plzeňský", 49.3958, 13.2947),
    "Kutná Hora": ("Středočeský", 49.9484, 15.2681),
    "Jindřichův Hradec": ("Jihočeský", 49.1441, 15.0030),
    "Náchod": ("Královéhradecký", 50.4155, 16.1657),
    "Vyškov": ("Jihomoravský", 49.2775, 16.9988),
    "Strakonice": ("Jihočeský", 49.2619, 13.9022),
    "Kralupy nad Vltavou": ("Středočeský", 50.2411, 14.3110),
    "Uherský Brod": ("Zlínský", 49.0255, 17.6470),
    "Beroun": ("Středočeský", 49.9636, 14.0722),
    "Louny": ("Ústecký", 50.3573, 13.7965),
    "Brandýs nad Labem-Stará Boleslav": ("Středočeský", 50.1861, 14.6614),
    "Bruntál": ("Moravskoslezský", 49.9884, 17.4646),
    "Litvínov": ("Ústecký", 50.6011, 13.6110),
    "Česká Třebová": ("Pardubický", 49.9008, 16.4470),
    "Nymburk": ("Středočeský", 50.1857, 15.0413),
    "Rakovník": ("Středočeský", 50.1039, 13.7336),
    "Chrudim": ("Pardubický", 49.9511, 15.7955),
    "Bohumín": ("Moravskoslezský", 49.9038, 18.3585),
    "Jirkov": ("Ústecký", 50.4986, 13.4479),
    "Orlová": ("Moravskoslezský", 49.8453, 18.4300),
    "Kopřivnice": ("Moravskoslezský", 49.5993, 18.1447),
    "Mělník": ("Středočeský", 50.3505, 14.4740),
    "Svitavy": ("Pardubický", 49.7554, 16.4691),
    "Vlašim": ("Středočeský", 49.7085, 14.8992),
    "Benešov": ("Středočeský", 49.7810, 14.6875),
    "Slaný": ("Středočeský", 50.2306, 14.0876),
    "Rokycany": ("Plzeňský", 49.7425, 13.5947),
    "Jičín": ("Královéhradecký", 50.4372, 15.3517),
    "Nový Bor": ("Liberecký", 50.7573, 14.5590),
    "Turnov": ("Liberecký", 50.5871, 15.1580),
    "Dvůr Králové nad Labem": ("Královéhradecký", 50.4324, 15.8140),
    "Domažlice": ("Plzeňský", 49.4406, 12.9294),
    "Tachov": ("Plzeňský", 49.7955, 12.6316),
    "Žatec": ("Ústecký", 50.3273, 13.5457),
    "Varnsdorf": ("Ústecký", 50.9124, 14.6182),
    "Krupka": ("Ústecký", 50.6847, 13.8578),
    "Roudnice nad Labem": ("Ústecký", 50.4256, 14.2611),
    "Nové Město na Moravě": ("Vysočina", 49.5614, 16.0740),
    "Pelhřimov": ("Vysočina", 49.4310, 15.2233),
    "Boskovice": ("Jihomoravský", 49.4874, 16.6597),
    "Kyjov": ("Jihomoravský", 49.0102, 17.1216),
    "Veselí nad Moravou": ("Jihomoravský", 48.9548, 17.3781),
    "Mikulov": ("Jihomoravský", 48.8058, 16.6383),
    "Velké Pavlovice": ("Jihomoravský", 48.9060, 16.8168),
    "Slavkov u Brna": ("Jihomoravský", 49.1531, 16.8760),
    "Bučovice": ("Jihomoravský", 49.1497, 17.0006),
    "Rožnov pod Radhoštěm": ("Zlínský", 49.4585, 18.1443),
    "Luhačovice": ("Zlínský", 49.1020, 17.7602),
    "Holešov": ("Zlínský", 49.3335, 17.5786),
    "Bystřice pod Hostýnem": ("Zlínský", 49.3993, 17.6741),
    "Jeseník": ("Olomoucký", 50.2236, 17.2044),
    "Zábřeh": ("Olomoucký", 49.8825, 16.8720),
    "Uničov": ("Olomoucký", 49.7714, 17.1216),
    "Litovel": ("Olomoucký", 49.7008, 17.0761),
    "Sušice": ("Plzeňský", 49.2311, 13.5220),
    "Prachatice": ("Jihočeský", 49.0130, 14.0000),
    "Český Krumlov": ("Jihočeský", 48.8109, 14.3175),
    "Třeboň": ("Jihočeský", 49.0033, 14.7700),
    "Vimperk": ("Jihočeský", 49.0517, 13.7739),
    "Milevsko": ("Jihočeský", 49.4519, 14.3603),
    "Dačice": ("Jihočeský", 49.0808, 15.4372),
    "Hluboká nad Vltavou": ("Jihočeský", 49.0512, 14.4344),
    "Ždírec nad Doubravou": ("Vysočina", 49.6944, 15.8130),
    "Poděbrady": ("Středočeský", 50.1425, 15.1190),
    "Čáslav": ("Středočeský", 49.9110, 15.3922),
    "Neratovice": ("Středočeský", 50.2592, 14.5175),
    "Říčany": ("Středočeský", 49.9920, 14.6540),
    "Dobříš": ("Středočeský", 49.7809, 14.1707),
    "Sedlčany": ("Středočeský", 49.6603, 14.4270),
    "Votice": ("Středočeský", 49.6395, 14.6390),
    "Hořovice": ("Středočeský", 49.8339, 13.9036),
    "Vysoké Mýto": ("Pardubický", 49.9530, 16.1611),
    "Litomyšl": ("Pardubický", 49.8688, 16.3130),
    "Ústí nad Orlicí": ("Pardubický", 49.9738, 16.3937),
    "Lanškroun": ("Pardubický", 49.9122, 16.6130),
    "Přelouč": ("Pardubický", 50.0397, 15.5615),
    "Rychnov nad Kněžnou": ("Královéhradecký", 50.1636, 16.2757),
    "Nové Město nad Metují": ("Královéhradecký", 50.3446, 16.1517),
    "Broumov": ("Královéhradecký", 50.5857, 16.3320),
    "Vrchlabí": ("Královéhradecký", 50.6270, 15.6110),
    "Nová Paka": ("Královéhradecký", 50.4944, 15.5150),
    "Frýdlant": ("Liberecký", 50.9214, 15.0797),
    "Semily": ("Liberecký", 50.6033, 15.3369),
    "Jilemnice": ("Liberecký", 50.6100, 15.5070),
    "Železný Brod": ("Liberecký", 50.6430, 15.2540),
    "Aš": ("Karlovarský", 50.2244, 12.1949),
    "Mariánské Lázně": ("Karlovarský", 49.9646, 12.7009),
    "Ostrov": ("Karlovarský", 50.3060, 12.9400),
    "Chodov": ("Karlovarský", 50.2410, 12.7460),
    "Klášterec nad Ohří": ("Ústecký", 50.3846, 13.1720),
    "Kadaň": ("Ústecký", 50.3763, 13.2716),
    "Bílina": ("Ústecký", 50.5497, 13.7760),
    "Duchcov": ("Ústecký", 50.6042, 13.7450),
    "Rumburk": ("Ústecký", 50.9520, 14.5560),
    "Šternberk": ("Olomoucký", 49.7284, 17.2980),
    "Mohelnice": ("Olomoucký", 49.7772, 16.9188),
    "Fulnek": ("Moravskoslezský", 49.7127, 17.9040),
    "Frenštát pod Radhoštěm": ("Moravskoslezský", 49.5470, 18.2130),
    "Studénka": ("Moravskoslezský", 49.7230, 18.0800),
    "Odry": ("Moravskoslezský", 49.6620, 17.8300),
    "Vratimov": ("Moravskoslezský", 49.7710, 18.3090),
    "Šlapanice": ("Jihomoravský", 49.1670, 16.7250),
    "Ivančice": ("Jihomoravský", 49.1010, 16.3770),
    "Tišnov": ("Jihomoravský", 49.3490, 16.4250),
    "Moravský Krumlov": ("Jihomoravský", 49.0490, 16.3110),
    "Hustopeče": ("Jihomoravský", 48.9410, 16.7370),
}

# Common spelling / diacritic-free aliases -> canonical key.
ALIASES: dict[str, str] = {
    "praha 1": "Praha", "praha 2": "Praha", "praha 3": "Praha",
    "hl. m. praha": "Praha", "hlavni mesto praha": "Praha",
    "budejovice": "České Budějovice",
    "hradec kralove": "Hradec Králové",
    "usti nad labem": "Ústí nad Labem",
    "karlovy vary": "Karlovy Vary",
    "frydek mistek": "Frýdek-Místek",
    "brandys nad labem": "Brandýs nad Labem-Stará Boleslav",
}


def _norm(name: str) -> str:
    """Lowercase, strip diacritics and collapse whitespace for lookup."""
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    return " ".join(n.lower().replace("-", " ").split())


# Precompute a diacritic-free index of the canonical table once.
_INDEX: dict[str, str] = {_norm(k): k for k in CITIES}
_INDEX.update({_norm(k): v for k, v in ALIASES.items()})


def resolve_city(name: str) -> Optional[str]:
    """Return the canonical city key for a free-text town name, or ``None``."""
    key = _norm(name)
    if not key:
        return None
    if key in _INDEX:
        return _INDEX[key]
    # Try dropping a trailing parenthetical or "okres ..." suffix.
    head = key.split("(")[0].split(",")[0].strip()
    return _INDEX.get(head)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@lru_cache(maxsize=4096)
def region_for(name: str) -> Optional[str]:
    key = resolve_city(name)
    return CITIES[key][0] if key else None


@lru_cache(maxsize=4096)
def km_from_prague(name: str) -> Optional[int]:
    """Approximate straight-line km from Prague, rounded to the nearest km."""
    key = resolve_city(name)
    if not key:
        return None
    _, lat, lon = CITIES[key]
    return round(_haversine_km(PRAGUE_LAT, PRAGUE_LON, lat, lon))
