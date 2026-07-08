#!/usr/bin/env bash
# One-command bootstrap + run for the LuckySings CZ contact crawler.
# Requires an environment with OPEN (Unrestricted) network egress — see README.
#
#   bash tools/cz_contacts/run.sh            # full crawl
#   bash tools/cz_contacts/run.sh --limit 15 # quick smoke run
#
# Extra args are passed straight through to `python -m crawler`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "==> Checking outbound network access…"
if ! python3 - <<'PY'
import sys, urllib.request
try:
    urllib.request.urlopen("https://example.com", timeout=15)
    print("    network OK")
except Exception as e:
    print(f"    NO OUTBOUND ACCESS: {e}", file=sys.stderr)
    print("    This environment cannot reach the open web. Create an "
          "environment with Unrestricted network access and rerun.",
          file=sys.stderr)
    sys.exit(2)
PY
then
    exit 2
fi

echo "==> Installing dependencies…"
pip install -q -r requirements.txt

echo "==> Running crawler (this can take 2-6 hours with throttling)…"
python3 -m crawler --out-dir output "$@"

echo "==> Done. Outputs:"
ls -la output/ 2>/dev/null || true
