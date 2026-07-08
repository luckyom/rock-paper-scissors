#!/usr/bin/env bash
# One-command bootstrap + run for the LuckySings CZ contact crawler.
#
#   bash tools/cz_contacts/run.sh            # full crawl
#   bash tools/cz_contacts/run.sh --limit 15 # quick smoke run
#
# Extra args are passed straight through to `python -m crawler`.
# Works on macOS/Linux with a normal internet connection. Creates a local
# virtualenv (.venv) so it never touches your system Python, and wires up the
# certifi CA bundle so TLS verification works even on python.org macOS builds.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

PY="${PYTHON:-python3}"
echo "==> Python: $("$PY" --version 2>&1)"

echo "==> Creating virtualenv (.venv)…"
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies…"
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

# Point TLS at the certifi bundle so urllib AND requests verify correctly.
CERTIFI_PATH="$(python -c 'import certifi; print(certifi.where())')"
export SSL_CERT_FILE="$CERTIFI_PATH"
export REQUESTS_CA_BUNDLE="$CERTIFI_PATH"
echo "==> Using CA bundle: $CERTIFI_PATH"

echo "==> Checking outbound network access…"
python - <<'PY'
import sys, requests
try:
    r = requests.get("https://example.com", timeout=20)
    print(f"    network OK (HTTP {r.status_code})")
except Exception as e:
    print(f"    NETWORK CHECK FAILED: {e}", file=sys.stderr)
    print("    If this is a TLS error, run macOS 'Install Certificates.command' "
          "for your Python, or report this output.", file=sys.stderr)
    sys.exit(2)
PY

echo "==> Running crawler (full crawl can take 2-6 h with throttling)…"
python -m crawler --out-dir output "$@"

echo "==> Done. Outputs:"
ls -la output/ 2>/dev/null || true
