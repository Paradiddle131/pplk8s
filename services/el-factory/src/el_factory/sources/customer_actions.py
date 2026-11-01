"""A deterministic synthetic stream of customer actions (semantic/PLAN.md SL-8, SL-15): site
sessions that walk the funnel page view -> add to cart -> checkout, and CRM actions (an email
opened, a support contact), for the customers of the sales source.

The stream is append-only and extracted by the time an action was received, not when it happened:
most actions arrive within minutes, some a day late, so an extract holds actions of the day before
and silver has to merge them into their own event date. Each event day is generated from its own
seed, so an action never depends on the interval that requested it.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta

from el_factory.model import Interval, Page, Table
from el_factory.sources.base import Entity
from el_factory.sources.paging import paginate
from el_factory.sources.synthetic import CUSTOMER_COUNT

SOURCE = "synthetic"
SITE_STEPS = ("page_view", "add_to_cart", "checkout")
CRM_ACTIONS = ("email_open", "support_contact")
ACTION_TYPES = SITE_STEPS + CRM_ACTIONS
# The share of sessions that take the next step, after a page view and after an add to cart.
NEXT_STEP_RATE = {"page_view": 0.35, "add_to_cart": 0.5}
LATE_RATE = 0.08
# An action is received up to this long after it happened (a late one: a day plus a few hours).
MAX_LATENESS = timedelta(days=1, hours=6)

CUSTOMER_ACTIONS_TABLE = Table(
    "synthetic_customer_actions",
    (
        ("event_id", "text"),
        ("customer_id", "integer"),
        ("session_id", "text"),
        ("action_type", "text"),
        ("channel", "text"),
        ("event_ts", "timestamptz"),
        ("received_ts", "timestamptz"),
    ),
)


def entities(page_size: int) -> list[Entity]:
    def fetch(interval: Interval, cursor: int) -> Page:
        return paginate(build_customer_actions(interval), cursor, page_size)

    return [Entity(SOURCE, "customer_actions", CUSTOMER_ACTIONS_TABLE, fetch)]


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _received(rng: random.Random, event_ts: datetime) -> datetime:
    if rng.random() < LATE_RATE:
        return event_ts + timedelta(days=1, seconds=rng.randint(0, 6 * 3_600))
    return event_ts + timedelta(seconds=rng.randint(1, 300))


def _day_actions(day: date) -> list[dict[str, object]]:
    """Every action that happened on ``day``, with when it was received."""
    rng = random.Random(f"customer_actions:{day.isoformat()}")
    midnight = _midnight(day)
    events: list[tuple[int, str | None, str, str, datetime]] = []
    for session in range(1, 30 + rng.randint(0, 30) + 1):
        customer_id = rng.randint(1, CUSTOMER_COUNT)
        session_id = f"S-{day:%Y%m%d}-{session:04d}"
        at = midnight + timedelta(seconds=rng.randint(0, 86_399))
        for step in SITE_STEPS:
            events.append((customer_id, session_id, step, "site", at))
            if step not in NEXT_STEP_RATE or rng.random() >= NEXT_STEP_RATE[step]:
                break
            # The next step comes minutes later and may fall after midnight.
            at += timedelta(seconds=rng.randint(30, 1_800))
    for _ in range(10 + rng.randint(0, 15)):
        action = rng.choices(CRM_ACTIONS, (4, 1))[0]
        at = midnight + timedelta(seconds=rng.randint(0, 86_399))
        events.append((rng.randint(1, CUSTOMER_COUNT), None, action, "crm", at))
    return [
        {
            "event_id": f"E-{day:%Y%m%d}-{seq:05d}",
            "customer_id": customer_id,
            "session_id": session_id,
            "action_type": action,
            "channel": channel,
            "event_ts": at.isoformat(),
            "received_ts": _received(rng, at).isoformat(),
        }
        for seq, (customer_id, session_id, action, channel, at) in enumerate(events, start=1)
    ]


def build_customer_actions(interval: Interval) -> list[dict[str, object]]:
    """Actions received in [start, end), ordered by received_ts then id.

    A session generated on one day keeps that day's seed even when a step falls after midnight.
    """
    first = (interval.start - MAX_LATENESS).astimezone(UTC).date() - timedelta(days=1)
    last = interval.end.astimezone(UTC).date()
    rows = [
        row
        for offset in range((last - first).days + 1)
        for row in _day_actions(first + timedelta(days=offset))
        if interval.start <= datetime.fromisoformat(str(row["received_ts"])) < interval.end
    ]
    return sorted(rows, key=lambda r: (r["received_ts"], r["event_id"]))
