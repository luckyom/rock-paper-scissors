"""Discover the venue master list.

Primary source: the NIPOS directory XLS. We locate a spreadsheet link on the
NIPOS listing pages, download it, and parse venue rows (name, city, website).
Secondary: harvest venue links from the cross-reference directories.

If NIPOS is unreachable or its format changes, ``load_seed_csv`` lets you feed a
hand/­search-built ``data/venues.csv`` instead — the rest of the pipeline is
identical.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from . import config
from .extract import domain_of
from .http import Fetcher

_SHEET_LINK_RE = re.compile(r"\.(xlsx?|csv)(\?|$)", re.I)

# Column-name heuristics for the NIPOS sheet (Czech headers vary by year).
_NAME_COLS = ["název", "nazev", "organizace", "zařízení", "zarizeni", "instituce"]
_CITY_COLS = ["obec", "město", "mesto", "sídlo", "sidlo", "místo", "misto"]
_WEB_COLS = ["web", "www", "url", "stránky", "stranky", "internet"]


def _pick_col(cols: list[str], wanted: list[str]) -> Optional[str]:
    low = {c.lower().strip(): c for c in cols}
    for w in wanted:
        for lc, orig in low.items():
            if w in lc:
                return orig
    return None


def find_spreadsheet_urls(fetcher: Fetcher, listing_urls=None) -> list[str]:
    listing_urls = listing_urls or config.NIPOS_LISTING_URLS
    found: list[str] = []
    for url in listing_urls:
        res = fetcher.get(url)
        if res.status != 200 or not res.text:
            continue
        soup = BeautifulSoup(res.text, "lxml")
        for a in soup.find_all("a", href=True):
            if _SHEET_LINK_RE.search(a["href"]):
                found.append(urljoin(res.final_url or url, a["href"]))
    # de-dup, preserve order
    seen, out = set(), []
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def parse_spreadsheet(raw: bytes, url: str) -> list[dict]:
    """Parse an XLS/XLSX/CSV byte blob into venue dicts."""
    df: Optional[pd.DataFrame] = None
    if url.lower().split("?")[0].endswith(".csv"):
        for enc in ("utf-8-sig", "cp1250", "utf-8"):
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding=enc, sep=None, engine="python")
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
    else:
        df = pd.read_excel(io.BytesIO(raw))  # needs openpyxl/xlrd
    if df is None or df.empty:
        return []

    cols = [str(c) for c in df.columns]
    name_c = _pick_col(cols, _NAME_COLS)
    city_c = _pick_col(cols, _CITY_COLS)
    web_c = _pick_col(cols, _WEB_COLS)
    if not name_c:
        return []

    out = []
    for _, row in df.iterrows():
        name = str(row.get(name_c, "")).strip()
        if not name or name.lower() == "nan":
            continue
        out.append(
            {
                "organization": name,
                "city": ("" if not city_c else str(row.get(city_c, "")).strip()).replace("nan", ""),
                "website": ("" if not web_c else str(row.get(web_c, "")).strip()).replace("nan", ""),
            }
        )
    return out


def discover_nipos(fetcher: Fetcher) -> list[dict]:
    venues: list[dict] = []
    for sheet_url in find_spreadsheet_urls(fetcher):
        # Download raw bytes (bypass the text cache for binary).
        try:
            resp = fetcher.session.get(sheet_url, timeout=30)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        try:
            venues.extend(parse_spreadsheet(resp.content, sheet_url))
        except Exception:
            continue
    return venues


def load_seed_csv(path: str | Path) -> list[dict]:
    """Load a hand/search-built venue list: columns organization,city,website[,events]."""
    p = Path(path)
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            org = (row.get("organization") or "").strip()
            if not org:
                continue
            out.append(
                {
                    "organization": org,
                    "city": (row.get("city") or "").strip(),
                    "website": (row.get("website") or "").strip(),
                    "events": (row.get("events") or "").strip(),
                }
            )
    return out


def dedup_venues(venues: Iterator[dict]) -> list[dict]:
    seen, out = set(), []
    for v in venues:
        key = domain_of(v.get("website", "")) or (v["organization"].lower(), v.get("city", "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out
