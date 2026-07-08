"""Row schema for the contact database."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

# Output column order — matches the task spec exactly.
COLUMNS = [
    "category",
    "organization",
    "city",
    "region",
    "km_from_Prague",
    "person_name",
    "person_title",
    "email",
    "phone",
    "contact_type",   # DRAMATURG / DIRECTOR / GENERIC / FORM
    "website",
    "source_url",
    "events_they_run",
    "priority",       # A / B / C
    "notes",
]

# Category labels.
CAT_KD = "Kulturní dům / MKS"
CAT_FESTIVAL = "Městské slavnosti / vinobraní"
CAT_XMAS = "Vánoční trhy"
CAT_AGENCY = "Event agentura"
CAT_WEDDING = "Svatební agentura / místo"

# contact_type tiers
T_DRAMATURG = "DRAMATURG"
T_DIRECTOR = "DIRECTOR"
T_GENERIC = "GENERIC"
T_FORM = "FORM"


@dataclass
class Contact:
    category: str
    organization: str
    city: str = ""
    region: str = ""
    km_from_Prague: Optional[int] = None
    person_name: str = ""
    person_title: str = ""
    email: str = ""
    phone: str = ""
    contact_type: str = ""
    website: str = ""
    source_url: str = ""
    events_they_run: str = ""
    priority: str = ""
    notes: str = ""

    def dedup_key(self) -> tuple:
        """Deduplicate by (domain, person-or-email).

        When neither a domain nor a person/email is known yet (e.g. an
        unresolved Christmas-market row awaiting an organizer site), fall back
        to (organization, city) so distinct orgs are not collapsed together.
        """
        from .extract import domain_of
        dom = domain_of(self.website or self.source_url or self.email)
        who = (self.person_name.strip().lower() or self.email.strip().lower())
        if not dom and not who:
            return ("org:" + self.organization.strip().lower(),
                    self.city.strip().lower())
        return (dom, who)

    def as_row(self) -> dict:
        return {k: (v if v is not None else "") for k, v in asdict(self).items()}
