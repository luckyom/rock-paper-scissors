"""Offline tests — exercise extraction, resolution and output with no network.

Run:  cd tools/cz_contacts && python -m pytest -q   (or python tests/test_crawler.py)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crawler import extract, geo                         # noqa: E402
from crawler.models import Contact, CAT_KD, CAT_XMAS     # noqa: E402
from crawler.output import contacts_to_frame, write_outputs, _top50_frame  # noqa: E402
from crawler.resolve import resolve_org                  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


# --- a fake fetcher that serves fixture files instead of the network -------
class FakeFetch:
    def __init__(self, pages: dict):
        self.pages = pages           # url -> html

    def get(self, url, use_cache=True):
        from crawler.http import FetchResult
        html = self.pages.get(url)
        if html is None:
            return FetchResult(url, 404, "", from_cache=False)
        return FetchResult(url, 200, html, from_cache=False, final_url=url)


def _cfemail_token(addr: str, key: int = 0x42) -> str:
    out = f"{key:02x}"
    for ch in addr:
        out += f"{ord(ch) ^ key:02x}"
    return out


# --- email extraction ------------------------------------------------------
def test_plain_and_mailto_emails():
    html = (FIX / "kd_dramaturg.html").read_text(encoding="utf-8")
    emails = extract.emails_from_html(html)
    assert "j.novakova@kdplzen.cz" in emails
    assert "reditel@kdplzen.cz" in emails
    assert "info@kdplzen.cz" in emails


def test_obfuscated_text_email():
    emails = extract.emails_from_text("napište na info [zavináč] mksvsetin [tečka] cz prosím")
    assert "info@mksvsetin.cz" in emails


def test_cloudflare_decode():
    addr = "program@mksvsetin.cz"
    token = _cfemail_token(addr)
    html = f'<a class="__cf_email__" data-cfemail="{token}">[email protected]</a>'
    assert addr in extract.emails_from_html(html)


def test_no_guessed_email_when_absent():
    html = "<p>Ředitelka: Jana Nováková, tel. 777 111 222</p>"
    assert extract.emails_from_html(html) == []   # never fabricates from a name


def test_junk_filtered():
    html = '<img src="logo.png"> <a href="mailto:you@example.com">x</a>'
    assert extract.emails_from_html(html) == []


# --- phones ----------------------------------------------------------------
def test_phone_normalisation():
    ph = extract.phones_from_text("volejte +420 377 123 456 nebo 377987654")
    assert "+420 377 123 456" in ph
    assert "+420 377 987 654" in ph


# --- named-contact tiering -------------------------------------------------
def test_named_contacts_prefers_dramaturg():
    html = (FIX / "kd_dramaturg.html").read_text(encoding="utf-8")
    named = extract.find_named_contacts(html)
    assert named, "should find named contacts"
    assert named[0]["tier"] == "DRAMATURG"
    assert named[0]["email"] == "j.novakova@kdplzen.cz"
    assert "Jana Nováková" in named[0]["person_name"]


# --- geo -------------------------------------------------------------------
def test_geo_lookup():
    assert geo.region_for("Plzeň") == "Plzeňský"
    assert geo.region_for("Vsetín") == "Zlínský"
    assert geo.km_from_prague("Praha") == 0
    d = geo.km_from_prague("Brno")
    assert 170 < d < 200            # ~184 km straight line
    assert geo.region_for("Neznámé Město") is None


def test_geo_diacritic_insensitive():
    assert geo.region_for("plzen") == "Plzeňský"


# --- resolution ------------------------------------------------------------
def test_resolve_picks_dramaturg_and_priority_A():
    url = "https://kdplzen.cz"
    pages = {url: (FIX / "kd_dramaturg.html").read_text(encoding="utf-8")}
    ff = FakeFetch(pages)
    c = resolve_org(ff, category=CAT_KD, organization="KD Plzeň",
                    city="Plzeň", website="kdplzen.cz")
    assert c.contact_type == "DRAMATURG"
    assert c.email == "j.novakova@kdplzen.cz"
    assert c.region == "Plzeňský"
    assert c.priority == "A"        # dramaturg within 100 km? Plzeň ~ 84 km


def test_resolve_form_only():
    url = "https://dkmetropol.cz"
    pages = {url: (FIX / "kd_form_only.html").read_text(encoding="utf-8")}
    ff = FakeFetch(pages)
    c = resolve_org(ff, category=CAT_KD, organization="DK Metropol",
                    city="České Budějovice", website="dkmetropol.cz")
    assert c.contact_type == "FORM"
    assert "/odeslat-zpravu" in c.source_url


def test_resolve_xmas_priority_A_on_generic():
    url = "https://mestoxyz.cz"
    pages = {url: '<p>Kontakt: <a href="mailto:info@mestoxyz.cz">info@mestoxyz.cz</a></p>'}
    ff = FakeFetch(pages)
    c = resolve_org(ff, category=CAT_XMAS, organization="Vánoční trhy XYZ",
                    city="Liberec", website="mestoxyz.cz")
    assert c.email == "info@mestoxyz.cz"
    assert c.priority == "A"        # any resolved xmas email is send-first


# --- output ----------------------------------------------------------------
def test_output_files(tmp_path):
    contacts = [
        Contact(category=CAT_KD, organization="A", city="Plzeň", region="Plzeňský",
                km_from_Prague=84, person_name="X", email="a@a.cz",
                contact_type="DRAMATURG", priority="A", website="a.cz", source_url="a.cz"),
        Contact(category=CAT_XMAS, organization="B", city="Brno", region="Jihomoravský",
                km_from_Prague=184, email="b@b.cz", contact_type="GENERIC",
                priority="A", website="b.cz", source_url="b.cz"),
        Contact(category=CAT_KD, organization="C", city="Ostrava", region="Moravskoslezský",
                km_from_Prague=280, email="c@c.cz", contact_type="GENERIC",
                priority="C", website="c.cz", source_url="c.cz"),
    ]
    res = write_outputs(contacts, tmp_path)
    assert Path(res["xlsx"]).exists()
    assert Path(res["csv"]).exists()
    assert res["rows"] == 3
    assert res["priority_A"] == 2

    df = contacts_to_frame(contacts)
    top = _top50_frame(df)
    assert list(top["organization"]) == ["A", "B"]   # A-priority, sorted by km


def test_dedup_keeps_distinct_websiteless_orgs():
    # Two unresolved xmas rows with no website/email must not collapse.
    a = Contact(category=CAT_XMAS, organization="Vánoční trhy Brno", city="Brno")
    b = Contact(category=CAT_XMAS, organization="Vánoční trhy Zlín", city="Zlín")
    assert a.dedup_key() != b.dedup_key()
    # Same org+city collapse.
    c = Contact(category=CAT_XMAS, organization="Vánoční trhy Brno", city="Brno")
    assert a.dedup_key() == c.dedup_key()
    # Same domain, same person collapse regardless of source page.
    d = Contact(category=CAT_KD, organization="KD", website="x.cz",
                person_name="Jan Novák", email="jan@x.cz")
    e = Contact(category=CAT_KD, organization="KD web2", website="https://www.x.cz/kontakt",
                person_name="Jan Novák", email="jan@x.cz")
    assert d.dedup_key() == e.dedup_key()


def test_nipos_spreadsheet_parse():
    from crawler import discover
    csv_bytes = (
        "Název zařízení;Obec;Web\n"
        "Kulturní dům Beroun;Beroun;http://kdberoun.cz\n"
        "MěKS Vsetín;Vsetín;www.mksvsetin.cz\n"
    ).encode("utf-8")
    rows = discover.parse_spreadsheet(csv_bytes, "http://nipos.cz/adresar.csv")
    assert len(rows) == 2
    assert rows[0]["organization"] == "Kulturní dům Beroun"
    assert rows[0]["city"] == "Beroun"
    assert rows[1]["website"] == "www.mksvsetin.cz"


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    import tempfile
    passed = 0
    for fn in fns:
        try:
            if "tmp_path" in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            passed += 1
            print(f"PASS {fn.__name__}")
        except Exception:
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
