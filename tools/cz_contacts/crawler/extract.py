"""Extract *verified* contact details from an HTML page.

Every email returned by this module is one that literally appears on the page
(as text, a ``mailto:`` link, an HTML entity, or a common client-side
obfuscation that we decode). Nothing here ever synthesises ``name@domain`` from
a person's name — if the page does not contain an address, none is returned.
"""

from __future__ import annotations

import html
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
# A deliberately strict address pattern; TLD 2-24 chars.
EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}"
)

# Textual obfuscations seen on Czech venue sites, normalised before scanning.
_DEOBFUSCATIONS = [
    (re.compile(r"\s*\[\s*(?:at|zavináč|zavinac|@)\s*\]\s*", re.I), "@"),
    (re.compile(r"\s*\(\s*(?:at|zavináč|zavinac)\s*\)\s*", re.I), "@"),
    (re.compile(r"\s+(?:at|zavináč|zavinac)\s+", re.I), "@"),
    (re.compile(r"\s*\[\s*(?:dot|tečka|tecka)\s*\]\s*", re.I), "."),
    (re.compile(r"\s*\(\s*(?:dot|tečka|tecka)\s*\)\s*", re.I), "."),
    (re.compile(r"\s+(?:dot|tečka|tecka)\s+", re.I), "."),
]

# Addresses to ignore (asset filenames, sample/placeholder addresses).
_JUNK_LOCALPARTS = {"example", "email", "your", "name", "user", "info@example"}
_JUNK_DOMAINS = {"example.com", "example.org", "domain.com", "sentry.io", "wix.com"}
_JUNK_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")


def _clean_candidate(addr: str) -> Optional[str]:
    addr = addr.strip().strip(".,;:<>()[]\"'").lower()
    if not EMAIL_RE.fullmatch(addr):
        return None
    local, _, domain = addr.partition("@")
    if domain in _JUNK_DOMAINS or local in _JUNK_LOCALPARTS:
        return None
    if addr.endswith(_JUNK_EXT):
        return None
    if "@" not in addr or "." not in domain:
        return None
    return addr


def emails_from_text(text: str) -> list[str]:
    if not text:
        return []
    text = html.unescape(text)
    for pat, repl in _DEOBFUSCATIONS:
        text = pat.sub(repl, text)
    out: list[str] = []
    seen = set()
    for m in EMAIL_RE.findall(text):
        c = _clean_candidate(m)
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _decode_cloudflare(soup: BeautifulSoup) -> list[str]:
    """Decode Cloudflare ``data-cfemail`` email protection tokens."""
    out = []
    for el in soup.select("[data-cfemail]"):
        token = el.get("data-cfemail") or ""
        try:
            key = int(token[:2], 16)
            decoded = "".join(
                chr(int(token[i : i + 2], 16) ^ key) for i in range(2, len(token), 2)
            )
        except (ValueError, IndexError):
            continue
        c = _clean_candidate(decoded)
        if c:
            out.append(c)
    return out


def emails_from_html(html_text: str) -> list[str]:
    """All verifiable emails on a page: mailto links, cf-protected, and body text."""
    soup = BeautifulSoup(html_text, "lxml")
    found: list[str] = []
    seen = set()

    def add(addr: Optional[str]):
        if addr and addr not in seen:
            seen.add(addr)
            found.append(addr)

    for a in soup.select("a[href^=mailto], a[href^=MAILTO]"):
        href = a.get("href", "")
        addr = href.split(":", 1)[1].split("?", 1)[0] if ":" in href else ""
        add(_clean_candidate(addr))

    for addr in _decode_cloudflare(soup):
        add(addr)

    # Body text (obfuscation-aware). Drop script/style noise first.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for addr in emails_from_text(soup.get_text(" ")):
        add(addr)

    return found


# ---------------------------------------------------------------------------
# Phone (Czech formats)
# ---------------------------------------------------------------------------
_PHONE_RE = re.compile(
    r"(?<!\d)(?:(?:\+|00)\s?420[\s.\-]?)?(?:\d[\s.\-]?){8}\d(?!\d)"
)


def phones_from_text(text: str) -> list[str]:
    if not text:
        return []
    out, seen = [], set()
    for m in _PHONE_RE.findall(text):
        digits = re.sub(r"[^\d+]", "", m)
        core = digits.lstrip("+").removeprefix("00")
        if core.startswith("420"):
            core = core[3:]
        if len(core) != 9:      # Czech national numbers are 9 digits
            continue
        pretty = "+420 " + " ".join([core[0:3], core[3:6], core[6:9]])
        if pretty not in seen:
            seen.add(pretty)
            out.append(pretty)
    return out


# ---------------------------------------------------------------------------
# Contact-tier detection
# ---------------------------------------------------------------------------
# Keywords that identify a program/dramaturgy/production role (top tier).
DRAMATURG_KW = [
    "dramaturg", "dramaturgie", "program", "programov", "produkce",
    "produkční", "produkcni", "vedoucí programu", "manažer kultury",
    "kulturní referent", "kulturni referent",
]
DIRECTOR_KW = ["ředitel", "reditel", "ředitelka", "reditelka", "jednatel"]

_TITLE_HINT_RE = re.compile(
    r"(ředitel\w*|reditel\w*|dramaturg\w*|produkc\w*|program\w*|"
    r"vedoucí\s+\w+|manaž\w*|referent\w*|jednatel\w*|kontaktní\s+osoba)",
    re.I,
)
# A Czech person name: a titled form (academic prefix) or two capitalised
# words where neither word is a common heading/role noun.
_TITLED_NAME_RE = re.compile(
    r"((?:Mgr\.|Ing\.|MgA\.|Bc\.|PhDr\.|MUDr\.|JUDr\.|doc\.|prof\.|BcA\.)\s*"
    r"[A-ZÁ-Ž][a-zá-ž]+\s+[A-ZÁ-Ž][a-zá-ž]+)"
)
_TWOWORD_NAME_RE = re.compile(r"([A-ZÁ-Ž][a-zá-ž]{1,}\s+[A-ZÁ-Ž][a-zá-ž]{1,})")

# Words that are NOT surnames — headings, roles, org-type nouns.
_NAME_STOP = {
    "kontakt", "kontakty", "sekretariat", "program", "programove", "dramaturgie",
    "produkce", "reditel", "reditelka", "vedeni", "adresa", "telefon", "email",
    "dum", "kultury", "kulturni", "mestske", "stredisko", "mesto", "urad",
    "obec", "spolecnost", "oddeleni", "provozni", "pokladna", "informace",
    "mgr", "ing", "mga", "bc", "phdr", "mudr", "doc", "prof", "napiste", "volejte",
}


def _find_person_name(text: str) -> str:
    m = _TITLED_NAME_RE.search(text)
    if m:
        return m.group(1).strip()
    for m in _TWOWORD_NAME_RE.finditer(text):
        w1, w2 = m.group(1).split(None, 1)
        if _norm_word(w1) in _NAME_STOP or _norm_word(w2) in _NAME_STOP:
            continue
        return m.group(1).strip()
    return ""


def _norm_word(w: str) -> str:
    import unicodedata
    n = unicodedata.normalize("NFKD", w)
    return "".join(c for c in n if not unicodedata.combining(c)).lower().strip(".")


def classify_contact_type(context: str) -> str:
    low = context.lower()
    if any(k in low for k in DRAMATURG_KW):
        return "DRAMATURG"
    if any(k in low for k in DIRECTOR_KW):
        return "DIRECTOR"
    return "GENERIC"


def find_named_contacts(html_text: str) -> list[dict]:
    """Return candidate {person_name, person_title, email, phone, tier} dicts.

    Heuristic: scan block-level elements; when a block contains an email AND a
    person-like name AND a role keyword, emit a named contact. Ordered so that
    DRAMATURG rows sort before DIRECTOR before GENERIC.
    """
    soup = BeautifulSoup(html_text, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    results: list[dict] = []
    seen_emails = set()

    for block in soup.find_all(["li", "tr", "p", "div", "td", "article", "section"]):
        text = block.get_text(" ", strip=True)
        if not text or len(text) > 600:
            continue
        block_emails = emails_from_html(str(block))
        # Only leaf-ish blocks: exactly one email keeps name↔email association
        # correct (multi-email containers are skipped in favour of their rows).
        if len(block_emails) != 1:
            continue
        title_m = _TITLE_HINT_RE.search(text)
        titled = _TITLED_NAME_RE.search(text)
        # A block is a *named* contact only if it carries a role keyword or an
        # academic-titled name. A bare pair of capitalised words is NOT trusted
        # as a name (that produced "Instagram Facebook" / "Kontaktní údaje").
        if not (title_m or titled):
            continue
        if titled:
            name = titled.group(1).strip()
        elif title_m:
            name = _find_person_name(text)   # role present → trust a plain name
        else:
            name = ""
        tier = classify_contact_type(text)
        email = block_emails[0]
        if email in seen_emails:
            continue
        seen_emails.add(email)
        phones = phones_from_text(text)
        results.append(
            {
                "person_name": name,
                "person_title": title_m.group(1).strip() if title_m else "",
                "email": email,
                "phone": phones[0] if phones else "",
                "tier": tier,
            }
        )

    order = {"DRAMATURG": 0, "DIRECTOR": 1, "GENERIC": 2}
    results.sort(key=lambda r: order.get(r["tier"], 3))
    return results


# ---------------------------------------------------------------------------
# Links / domains
# ---------------------------------------------------------------------------
_CONTACT_HINTS = ("kontakt", "kontakty", "o-nas", "o-nás", "vedeni", "vedení",
                  "tym", "tým", "lide", "lidé", "kdo-jsme")


def domain_of(url_or_email: str) -> str:
    if not url_or_email:
        return ""
    s = url_or_email.strip()
    if "@" in s and "://" not in s:
        return s.split("@")[-1].lower().lstrip("www.")
    host = urlparse(s if "://" in s else "http://" + s).hostname or ""
    return host.lower().removeprefix("www.")


def find_contact_page_links(html_text: str, base_url: str) -> list[str]:
    """Absolute URLs of likely 'kontakty'/'o nás'/'vedení' pages on the same host."""
    soup = BeautifulSoup(html_text, "lxml")
    base_host = domain_of(base_url)
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        text = (a.get_text(" ", strip=True) or "").lower()
        url = urljoin(base_url, href)
        if domain_of(url) != base_host:
            continue
        low_url = url.lower()
        if any(h in low_url for h in _CONTACT_HINTS) or any(
            h in text for h in ("kontakt", "vedení", "vedeni", "o nás", "tým", "team")
        ):
            if url not in seen:
                seen.add(url)
                out.append(url)
    return out


def find_contact_form(html_text: str, base_url: str) -> Optional[str]:
    """Return a contact-form URL if the page has a <form> but no email at all."""
    soup = BeautifulSoup(html_text, "lxml")
    forms = soup.find_all("form")
    for f in forms:
        blob = " ".join(
            (f.get("action", ""), f.get("id", ""), f.get("class", "") and " ".join(f.get("class")))
        ).lower()
        fields = " ".join(inp.get("name", "") for inp in f.find_all(["input", "textarea"])).lower()
        if any(k in blob + fields for k in ("kontakt", "contact", "message", "zprava", "zpráva", "email")):
            action = f.get("action") or ""
            return urljoin(base_url, action) if action else base_url
    return None
