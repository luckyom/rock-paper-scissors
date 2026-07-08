"""Resolve a single organization to its best booking contact.

Given a venue's name/city/website, fetch the homepage, follow up to a few
'kontakty'/'vedení' pages, and pick the best contact tier available:

    DRAMATURG > DIRECTOR > GENERIC email > FORM (contact form URL)

Assigns priority per the task's rules:
    A = named DRAMATURG within 100 km of Prague, or any Christmas-market /
        festival organizer contact
    B = a named contact (DRAMATURG/DIRECTOR) elsewhere
    C = generic email only
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from . import extract, geo
from .http import Fetcher
from .models import (
    Contact, T_DRAMATURG, T_DIRECTOR, T_GENERIC, T_FORM,
    CAT_XMAS, CAT_FESTIVAL,
)

MAX_CONTACT_PAGES = 4


def _norm_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def resolve_org(
    fetcher: Fetcher,
    *,
    category: str,
    organization: str,
    city: str = "",
    website: str = "",
    events_they_run: str = "",
    seed_source_url: str = "",
) -> Contact:
    """Crawl an org's site and return a populated Contact (best effort)."""
    region = geo.region_for(city) or ""
    km = geo.km_from_prague(city)
    website = _norm_url(website)

    contact = Contact(
        category=category,
        organization=organization,
        city=city,
        region=region,
        km_from_Prague=km,
        website=website,
        source_url=seed_source_url or website,
        events_they_run=events_they_run,
    )

    if not website:
        contact.contact_type = ""
        contact.notes = "No website known; needs manual lookup."
        contact.priority = "C"
        return contact

    pages: list[tuple[str, str]] = []  # (url, html)
    home = fetcher.get(website)
    if home.blocked_by_robots:
        contact.notes = "Homepage disallowed by robots.txt."
        contact.priority = "C"
        return contact
    if home.status == 200 and home.text:
        pages.append((home.final_url or website, home.text))
        for link in extract.find_contact_page_links(home.text, website)[:MAX_CONTACT_PAGES]:
            sub = fetcher.get(link)
            if sub.status == 200 and sub.text and not sub.blocked_by_robots:
                pages.append((sub.final_url or link, sub.text))
    else:
        contact.notes = f"Homepage fetch failed (status {home.status})."
        contact.priority = "C"
        return contact

    # 1) Best named contact across all fetched pages.
    best: Optional[dict] = None
    best_src = ""
    tier_rank = {"DRAMATURG": 0, "DIRECTOR": 1, "GENERIC": 2}
    for url, html_text in pages:
        for cand in extract.find_named_contacts(html_text):
            if best is None or tier_rank[cand["tier"]] < tier_rank[best["tier"]]:
                best = cand
                best_src = url
            if best and best["tier"] == "DRAMATURG":
                break
        if best and best["tier"] == "DRAMATURG":
            break

    if best:
        contact.person_name = best["person_name"]
        contact.person_title = best["person_title"]
        contact.email = best["email"]
        contact.phone = best["phone"]
        contact.contact_type = best["tier"]
        contact.source_url = best_src
        _assign_priority(contact)
        return contact

    # 2) No named contact — take any generic email from the pages.
    site_domain = extract.domain_of(website)
    for url, html_text in pages:
        emails = extract.emails_from_html(html_text)
        if emails:
            contact.email = _prefer_generic(emails, site_domain)
            contact.contact_type = T_GENERIC
            contact.source_url = url
            if site_domain and extract.domain_of(contact.email) != site_domain:
                contact.notes = (
                    f"Email domain differs from site ({site_domain}); verify."
                )
            phones = extract.phones_from_text(
                extract.BeautifulSoup(html_text, "lxml").get_text(" ")
            )
            if phones:
                contact.phone = phones[0]
            _assign_priority(contact)
            return contact

    # 3) No email anywhere — record a contact form if present.
    for url, html_text in pages:
        form = extract.find_contact_form(html_text, url)
        if form:
            contact.contact_type = T_FORM
            contact.source_url = form
            contact.notes = "No email published; contact form only."
            contact.priority = "C"
            return contact

    contact.notes = "No email or contact form found on site."
    contact.priority = "C"
    return contact


def _prefer_generic(emails: list[str], site_domain: str = "") -> str:
    """Pick the best generic address.

    Prefer an address on the site's own domain (avoids grabbing a partner/agency
    address embedded in a footer), then an info@/kultura@/podatelna@ localpart.
    """
    same = [e for e in emails if site_domain and extract.domain_of(e) == site_domain]
    pool = same or emails
    priority_locals = ("info", "kultura", "kancelar", "sekretariat", "podatelna", "mesto", "urad")
    for pref in priority_locals:
        for e in pool:
            if e.split("@")[0].startswith(pref):
                return e
    return pool[0]


def _assign_priority(contact: Contact) -> None:
    """A / B / C per the spec."""
    is_event = contact.category in (CAT_XMAS, CAT_FESTIVAL)
    if contact.contact_type == T_DRAMATURG:
        near = contact.km_from_Prague is not None and contact.km_from_Prague <= 100
        contact.priority = "A" if (near or is_event) else "B"
    elif contact.contact_type == T_DIRECTOR:
        contact.priority = "A" if is_event else "B"
    elif is_event and contact.email:
        contact.priority = "A"       # any resolved festival/xmas email is send-first
    else:
        contact.priority = "C"
