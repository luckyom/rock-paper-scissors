"""CLI entry point: ``python -m crawler [options]``."""

from __future__ import annotations

import argparse

from .pipeline import run


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="crawler",
        description="Build the LuckySings CZ booking-contact database "
                    "(verified emails scraped from official sites).",
    )
    ap.add_argument("--data-dir", default="data", help="seed CSV directory")
    ap.add_argument("--out-dir", default="output", help="where XLSX/CSV are written")
    ap.add_argument("--cache-dir", default=None, help="page cache dir (default .cache/pages)")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap number of venues (for a quick smoke run)")
    ap.add_argument("--skip-nipos", action="store_true",
                    help="skip live NIPOS download; use data/venues.csv only")
    args = ap.parse_args()

    run(
        data_dir=args.data_dir,
        out_dir=args.out_dir,
        cache_dir=args.cache_dir,
        limit=args.limit,
        skip_nipos=args.skip_nipos,
    )


if __name__ == "__main__":
    main()
