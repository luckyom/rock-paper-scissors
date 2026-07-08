# LuckySings CZ booking-contact crawler

Builds `LuckySings_CZ_Contact_Database.xlsx` (+ CSV) of reachable Czech booking
contacts across five categories, with **verified emails scraped from official
websites — never guessed**.

Categories: Kulturní domy / MKS / DK · Městské slavnosti + vinobraní ·
Vánoční trhy organizers · Event agencies (live music) · Wedding agencies /
coordinators / venues.

---

## ⚠️ Read first: this needs open network egress

The crawler fetches hundreds of external websites. It was authored inside a
Claude Code **web** session whose network policy **blocks all outbound HTTPS**
(the egress proxy returns `403` for every host — nipos.cz, kudyznudy.cz, even
example.com). In that environment the crawl **cannot run** and no real data can
be produced; only `WebSearch` works there, which returns snippets, not the
verifiable email-bearing pages the "no guessed emails" rule requires.

To get real data, run it somewhere with open egress:

* **On your machine** (recommended — simplest), or
* **A re-provisioned Claude Code web environment** created with an
  open/unrestricted network policy
  (see <https://code.claude.com/docs/en/claude-code-on-the-web>). Then
  `python -m crawler` runs here exactly as below.

Everything except the live fetch is fully built and tested offline (15 unit
tests, green) — extraction, obfuscation decoding, tiering, priority, dedup,
XLSX/CSV output.

---

## Quick start

```bash
cd tools/cz_contacts
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# full run (downloads the NIPOS directory, crawls every venue + seeds)
python -m crawler --out-dir output

# quick smoke run capped at 15 venues
python -m crawler --limit 15 --out-dir output
```

Outputs land in `output/`:

* `LuckySings_CZ_Contact_Database.xlsx` — sheets **ALL**, **TOP 50**, **STATS**
* `LuckySings_CZ_Contact_Database.csv` — the same rows

Re-runs are **incremental**: every fetched page is cached under `.cache/pages/`,
so a second run only fetches what's new.

### CLI options

| flag | meaning |
|------|---------|
| `--out-dir DIR` | where the XLSX/CSV go (default `output/`) |
| `--data-dir DIR` | seed-CSV directory (default `data/`) |
| `--cache-dir DIR` | page cache (default `.cache/pages`, or `$CZ_CACHE_DIR`) |
| `--limit N` | cap venues for a quick pass |
| `--skip-nipos` | skip live NIPOS download, use `data/venues.csv` only |

---

## How it works

1. **Discover venues** — download the NIPOS *adresář kulturních domů/středisek*
   XLS from its listing pages (`crawler/discover.py`), parse name/city/website.
   Merge with any `data/venues.csv` you supply. Deduplicate by domain.
2. **Resolve each org** (`crawler/resolve.py`) — fetch the homepage, follow up
   to 4 `kontakty`/`vedení`/`o nás` pages, and pick the best contact:
   `DRAMATURG > DIRECTOR > GENERIC email > FORM`.
3. **Extract** (`crawler/extract.py`) — emails from `mailto:`, page text,
   Cloudflare `data-cfemail` tokens, and Czech textual obfuscation
   (`info [zavináč] x [tečka] cz`). Phones normalised to `+420 xxx xxx xxx`.
   Named contacts are tied to a person + role keyword. **No address is ever
   synthesised from a name.**
4. **Christmas markets & festivals** — the 20 largest cities are seeded for
   Vánoční trhy; add organizer sites you find by search to `data/xmas.csv` /
   `data/festivals.csv` and they get resolved the same way.
5. **Agencies & weddings** — the task seed list plus anything in
   `data/agencies.csv` / `data/weddings.csv`.
6. **Dedup + write** — dedup by `(domain, person|email)`, then emit XLSX + CSV.

### Priority (per spec)

* **A** — named DRAMATURG within 100 km of Prague, *or* any resolved
  Christmas-market / festival organizer email.
* **B** — a named contact (dramaturg/director) elsewhere.
* **C** — generic email or contact-form only.

### Politeness

`crawler/http.py` honours `robots.txt`, throttles to **1 request / 2 s per
domain**, sets a descriptive User-Agent, and trusts the agent-proxy CA bundle
when present. Every row records a `source_url`, so each contact is auditable.

---

## Feeding it search-discovered organizers

Christmas-market and festival organizers often have no single registry. The
intended workflow: use search (`"<city> vánoční trhy pořadatel"`,
`kudyznudy.cz`, `festivaly.net`) to find each organizer's official site, then
drop rows into `data/xmas.csv` / `data/festivals.csv` (format in
`data/README.md`). The crawler scrapes the verified email from those sites.

## JS-obfuscated pages

A few sites build their contact page entirely client-side. Uncomment
`playwright` in `requirements.txt`, `playwright install chromium`, and render
those URLs, then feed the rendered HTML through `crawler.extract`. The current
build already decodes the common non-JS obfuscations, which covers the large
majority of Czech venue sites.

## Tests

```bash
python tests/test_crawler.py      # 15 offline tests, no network required
# or, with pytest installed:
python -m pytest -q
```
