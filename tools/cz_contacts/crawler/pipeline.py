"""End-to-end orchestration: discover → resolve → dedup → write."""

from __future__ import annotations

import sys
from pathlib import Path

from . import config, discover
from .http import Fetcher
from .models import (
    Contact, CAT_KD, CAT_AGENCY, CAT_WEDDING, CAT_XMAS,
)
from .output import write_outputs
from .resolve import resolve_org


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _resolve_all(fetcher: Fetcher, category: str, seeds: list[dict], data_dir: Path,
                 seed_source: str = "") -> list[Contact]:
    out: list[Contact] = []
    total = len(seeds)
    for i, s in enumerate(seeds, 1):
        org = s.get("organization", "")
        _log(f"  [{category}] {i}/{total}: {org}")
        try:
            c = resolve_org(
                fetcher,
                category=category,
                organization=org,
                city=s.get("city", ""),
                website=s.get("website", ""),
                events_they_run=s.get("events", ""),
                seed_source_url=seed_source,
            )
        except Exception as exc:  # never let one bad site kill the run
            c = Contact(category=category, organization=org, city=s.get("city", ""),
                        website=s.get("website", ""), notes=f"resolve error: {exc}",
                        priority="C")
        out.append(c)
    return out


def run(data_dir: str | Path = "data", out_dir: str | Path = "output",
        cache_dir: str | Path | None = None, limit: int | None = None,
        skip_nipos: bool = False) -> dict:
    data_dir = Path(data_dir)
    fetcher = Fetcher(cache_dir=Path(cache_dir) if cache_dir else None)
    contacts: list[Contact] = []

    # 1) Venues: NIPOS master + optional local seed CSV.
    venues: list[dict] = []
    if not skip_nipos:
        _log("Discovering NIPOS venue directory…")
        try:
            venues += discover.discover_nipos(fetcher)
        except Exception as exc:
            _log(f"  NIPOS discovery failed: {exc}")
    venues += discover.load_seed_csv(data_dir / "venues.csv")
    venues = discover.dedup_venues(venues)
    if limit:
        venues = venues[:limit]
    _log(f"Venues to resolve: {len(venues)}")
    contacts += _resolve_all(fetcher, CAT_KD, venues, data_dir,
                             seed_source="https://www.nipos.cz/1814/")

    # 2) Christmas markets (≈20 cities) + any search-built xmas.csv.
    xmas = discover.load_seed_csv(data_dir / "xmas.csv")
    known = {x["city"] for x in xmas}
    for city in config.XMAS_CITIES:
        if city not in known:
            xmas.append({"organization": f"Vánoční trhy {city}", "city": city,
                         "website": "", "events": "Vánoční trhy"})
    contacts += _resolve_all(fetcher, CAT_XMAS, xmas, data_dir)

    # 3) City festivals / vinobraní (search-built festivals.csv).
    festivals = discover.load_seed_csv(data_dir / "festivals.csv")
    from .models import CAT_FESTIVAL
    contacts += _resolve_all(fetcher, CAT_FESTIVAL, festivals, data_dir)

    # 4) Agencies (seed + directory-built agencies.csv).
    agencies = list(config.AGENCY_SEEDS) + discover.load_seed_csv(data_dir / "agencies.csv")
    contacts += _resolve_all(fetcher, CAT_AGENCY, agencies, data_dir)

    # 5) Weddings (seed + directory-built weddings.csv).
    weddings = list(config.WEDDING_SEEDS) + discover.load_seed_csv(data_dir / "weddings.csv")
    contacts += _resolve_all(fetcher, CAT_WEDDING, weddings, data_dir)

    # 6) Dedup by (domain, person/email) and write.
    seen, deduped = set(), []
    for c in contacts:
        key = c.dedup_key()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    _log(f"Total unique contacts: {len(deduped)}")
    result = write_outputs(deduped, out_dir)
    _log(f"Wrote {result['rows']} rows → {result['xlsx']}")
    _log(f"  priority A: {result['priority_A']} | with email: {result['with_email']}")
    return result
