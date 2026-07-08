"""Seed lists and source configuration.

Seeds are *public facts* — an organization name, its city, and (where known) its
official website URL. They are the crawl's starting points; all emails/phones
are scraped from the sites at run time, never taken from here.
"""

from __future__ import annotations

# --- NIPOS master directory ------------------------------------------------
# The NIPOS "adresář kulturních domů, středisek a osvětových zařízení" is
# published as an XLS on these listing pages. The downloader scans them for a
# .xls/.xlsx/.csv link and parses the first sheet.
NIPOS_LISTING_URLS = [
    "https://www.nipos.cz/1814/",          # Kulturní domy, střediska
    "https://www.nipos.cz/1819/",          # Magistráty
]

# --- Cross-reference directories -------------------------------------------
DIRECTORY_SOURCES = [
    "https://www.kulturnimapa.cz",
    "https://www.informuji.cz",
]

# --- Christmas-market cities (≈20 largest that run one) ---------------------
# The crawler resolves each to its organizer contact. Where the usual organizer
# site is publicly known it is given as a hint; otherwise the city domain is a
# fallback and search-derived organizer URLs can be added to data/xmas.csv.
XMAS_CITIES = [
    "Praha", "Brno", "Ostrava", "Plzeň", "Liberec", "Olomouc",
    "České Budějovice", "Hradec Králové", "Ústí nad Labem", "Pardubice",
    "Zlín", "Havířov", "Kladno", "Most", "Opava", "Karlovy Vary",
    "Jihlava", "Teplice", "Děčín", "Mladá Boleslav",
]

# --- Event agencies booking live music (task seed list, extend via crawl) --
# Only names + official sites; emails are scraped at run time.
AGENCY_SEEDS = [
    {"organization": "Živý Jukebox", "city": "Praha", "website": "zivyjukebox.cz"},
    {"organization": "OMT (One Man Team)", "city": "Praha", "website": "omt.cz"},
    {"organization": "NA-PÁRTY", "city": "Praha", "website": "na-party.cz"},
]

# --- Wedding agencies / coordinators / top venues (task seed, extend) ------
WEDDING_SEEDS = [
    {"organization": "Proweddy", "city": "Praha", "website": "proweddy.cz"},
]

# Directory/aggregator sites to expand agency & wedding coverage. The crawler
# harvests same-topic vendor links from these listing pages.
AGENCY_DIRECTORY_SOURCES = [
    "https://www.hudebni-skupiny.cz",
    "https://www.zabava-kapely.cz",
]
WEDDING_DIRECTORY_SOURCES = [
    "https://www.proweddy.cz/dodavatele",
    "https://www.svatba.cz/katalog",
]
