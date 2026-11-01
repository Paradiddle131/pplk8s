"""Deterministic synthetic partner outreach (semantic/PLAN.md SL-8, SL-16): the partners a services
business refers work with, their contacts with consent and opt-out flags, the messages an outreach
automation sends them, and the replies.

Contacts are a snapshot: every interval extracts each contact as it stood at the interval's end, so
a contact who opts out shows the opt-out from that interval on, with ``updated_ts`` saying when it
changed. Messages are extracted by the time they were sent and replies by the time they arrived, a
reply up to a few days after its message; each day is generated from its own seed, so a row never
depends on the interval that requested it. Contact details are personal data: a contact's name,
email and phone are synthetic, on the reserved ``example`` domain and the fictional 555 range.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta

from el_factory.model import Interval, Page, Table
from el_factory.sources.base import Entity, Fetch
from el_factory.sources.paging import paginate
from el_factory.sources.synthetic import FIRST_NAMES, LAST_NAMES

SOURCE = "synthetic"
# (partner_id, name, partner_type, country): fixed, so every interval sees the same partners.
PARTNERS = (
    (1, "Northwind Clinics", "clinic", "NL"),
    (2, "Bosphorus Health", "clinic", "TR"),
    (3, "Rhein Referrals", "agency", "DE"),
    (4, "Thames Partners", "agency", "GB"),
    (5, "Loire Wellness", "reseller", "FR"),
    (6, "Hudson Care Network", "reseller", "US"),
)
CONTACTS_PER_PARTNER = 3
CONTACTS_START = date(2026, 9, 1)
CONSENT_RATE = 0.85
# A consenting contact opts out on a day of OPT_OUT_DAYS after CONTACTS_START with this probability.
OPT_OUT_RATE = 0.25
OPT_OUT_DAYS = 90
CHANNELS = ("email", "phone", "sms")
REPLY_RATE = 0.3
MAX_REPLY_LAG_DAYS = 3

PARTNERS_TABLE = Table(
    "synthetic_partners",
    (
        ("partner_id", "integer"),
        ("name", "text"),
        ("partner_type", "text"),
        ("country", "text"),
    ),
)
CONTACTS_TABLE = Table(
    "synthetic_partner_contacts",
    (
        ("contact_id", "text"),
        ("partner_id", "integer"),
        ("contact_name", "text"),
        ("email", "text"),
        ("phone", "text"),
        ("preferred_channel", "text"),
        ("consent", "boolean"),
        ("opted_out_ts", "timestamptz"),
        ("updated_ts", "timestamptz"),
    ),
)
MESSAGES_TABLE = Table(
    "synthetic_outreach_messages",
    (
        ("message_id", "text"),
        ("contact_id", "text"),
        ("channel", "text"),
        ("sent_ts", "timestamptz"),
    ),
)
REPLIES_TABLE = Table(
    "synthetic_outreach_replies",
    (
        ("reply_id", "text"),
        ("message_id", "text"),
        ("replied_ts", "timestamptz"),
    ),
)


def entities(page_size: int) -> list[Entity]:
    def per_interval(build) -> Fetch:
        def fetch(interval: Interval, cursor: int) -> Page:
            return paginate(build(interval), cursor, page_size)

        return fetch

    return [
        Entity(SOURCE, "partners", PARTNERS_TABLE, per_interval(lambda _: build_partners())),
        Entity(SOURCE, "partner_contacts", CONTACTS_TABLE, per_interval(build_contacts)),
        Entity(SOURCE, "outreach_messages", MESSAGES_TABLE, per_interval(build_messages)),
        Entity(SOURCE, "outreach_replies", REPLIES_TABLE, per_interval(build_replies)),
    ]


def build_partners() -> list[dict[str, object]]:
    return [
        {"partner_id": partner_id, "name": name, "partner_type": kind, "country": country}
        for partner_id, name, kind, country in PARTNERS
    ]


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _contact(partner_id: int, seq: int) -> dict[str, object]:
    """A contact as the CRM holds it, with when it opts out (None: never), from its own seed."""
    contact_id = f"C-{partner_id:02d}{seq:02d}"
    rng = random.Random(f"partner_contact:{contact_id}")
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    consent = rng.random() < CONSENT_RATE
    opted_out = None
    if consent and rng.random() < OPT_OUT_RATE:
        opted_out = _midnight(CONTACTS_START) + timedelta(
            days=rng.randint(1, OPT_OUT_DAYS), seconds=rng.randint(0, 86_399)
        )
    return {
        "contact_id": contact_id,
        "partner_id": partner_id,
        "contact_name": f"{first} {last}",
        "email": f"{first}.{last.replace(' ', '')}@partner{partner_id}.example".lower(),
        "phone": f"+1-555-01{partner_id:01d}{seq:01d}",
        "preferred_channel": rng.choice(CHANNELS),
        "consent": consent,
        "opted_out_ts": opted_out,
    }


def _all_contacts() -> list[dict[str, object]]:
    return [
        _contact(partner_id, seq)
        for partner_id, *_ in PARTNERS
        for seq in range(1, CONTACTS_PER_PARTNER + 1)
    ]


def build_contacts(interval: Interval) -> list[dict[str, object]]:
    """Every contact as it stood at the interval's end: an opt-out shows once it has happened."""
    rows = []
    for contact in _all_contacts():
        opted_out = contact["opted_out_ts"]
        visible = isinstance(opted_out, datetime) and opted_out < interval.end
        rows.append(
            {
                **contact,
                "opted_out_ts": opted_out.isoformat() if visible else None,
                "updated_ts": (opted_out if visible else _midnight(CONTACTS_START)).isoformat(),
            }
        )
    return rows


def _reachable(contact: dict[str, object], at: datetime) -> bool:
    opted_out = contact["opted_out_ts"]
    return bool(contact["consent"]) and not (isinstance(opted_out, datetime) and opted_out <= at)


def _day_messages(day: date) -> list[dict[str, object]]:
    """The messages of ``day``: only to contacts who consented and had not opted out."""
    rng = random.Random(f"outreach_messages:{day.isoformat()}")
    contacts = _all_contacts()
    messages = []
    # One message per contact a day at most: the automation picks distinct contacts.
    for seq, contact in enumerate(rng.sample(contacts, 4 + rng.randint(0, 6)), start=1):
        sent = _midnight(day) + timedelta(seconds=rng.randint(8 * 3_600, 18 * 3_600))
        if not _reachable(contact, sent):
            continue
        messages.append(
            {
                "message_id": f"M-{day:%Y%m%d}-{seq:03d}",
                "contact_id": contact["contact_id"],
                "channel": contact["preferred_channel"],
                "sent_ts": sent.isoformat(),
            }
        )
    return messages


def _days_touching(interval: Interval, lookback_days: int = 0) -> list[date]:
    first = interval.start.astimezone(UTC).date() - timedelta(days=lookback_days)
    last = interval.end.astimezone(UTC).date()
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def build_messages(interval: Interval) -> list[dict[str, object]]:
    """Messages with sent_ts in [start, end), ordered by time then id."""
    rows = [
        message
        for day in _days_touching(interval)
        for message in _day_messages(day)
        if interval.start <= datetime.fromisoformat(str(message["sent_ts"])) < interval.end
    ]
    return sorted(rows, key=lambda r: (r["sent_ts"], r["message_id"]))


def _reply(message: dict[str, object]) -> dict[str, object] | None:
    """The reply a message gets, if any: decided by the message's own seed."""
    rng = random.Random(f"outreach_reply:{message['message_id']}")
    if rng.random() >= REPLY_RATE:
        return None
    sent = datetime.fromisoformat(str(message["sent_ts"]))
    replied = sent + timedelta(
        days=rng.randint(0, MAX_REPLY_LAG_DAYS), seconds=rng.randint(300, 6 * 3_600)
    )
    return {
        "reply_id": f"R-{str(message['message_id'])[2:]}",
        "message_id": message["message_id"],
        "replied_ts": replied.isoformat(),
    }


def build_replies(interval: Interval) -> list[dict[str, object]]:
    """Replies with replied_ts in [start, end), from messages up to the maximum lag before it."""
    replies = []
    for day in _days_touching(interval, lookback_days=MAX_REPLY_LAG_DAYS + 1):
        for message in _day_messages(day):
            reply = _reply(message)
            if reply and interval.start <= datetime.fromisoformat(str(reply["replied_ts"])) < (
                interval.end
            ):
                replies.append(reply)
    return sorted(replies, key=lambda r: (r["replied_ts"], r["reply_id"]))
