"""Deterministic synthetic marketing sources (PLAN.md D38): ad campaigns, their daily spend, the
CRM leads they bring, and the bookings those leads become.

The shape is a services business: a lead asks, a share of leads book within a few weeks, and a
booking is worth thousands, not tens. The source is `synthetic`, like the sales entities; each day
is generated from its own seed, so a row never depends on the interval that requested it.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from el_factory.model import Interval, Page, Table
from el_factory.sources.base import Entity, Fetch
from el_factory.sources.paging import paginate

SOURCE = "synthetic"
# (campaign_id, name, channel, market): fixed, so every interval sees the same campaigns.
CAMPAIGNS = (
    (1, "Search NL always-on", "search", "NL"),
    (2, "Search DE always-on", "search", "DE"),
    (3, "Search GB always-on", "search", "GB"),
    (4, "Social TR spring", "social", "TR"),
    (5, "Social FR autumn", "social", "FR"),
    (6, "Display retargeting", "display", "US"),
    (7, "Newsletter monthly", "email", "NL"),
    (8, "Partner referrals", "partner", "DE"),
)
CAMPAIGNS_START = date(2026, 1, 1)
# Daily spend per channel in cents (low, high); email and partner cost little per day.
SPEND_CENTS = {
    "search": (8_000, 30_000),
    "social": (5_000, 20_000),
    "display": (3_000, 12_000),
    "email": (500, 1_500),
    "partner": (1_000, 4_000),
}
BOOKING_RATE = 0.3
MAX_BOOKING_LAG_DAYS = 21
# The leads extract looks back past the longest booking lag, as a CRM extract re-reads recent
# records: every booking of an interval then names a lead the same run lands, so a fresh warehouse
# never holds a booking without its lead. Overlapping runs are idempotent (silver keeps the latest
# row per lead).
LEADS_LOOKBACK = timedelta(days=MAX_BOOKING_LAG_DAYS + 1)

CAMPAIGNS_TABLE = Table(
    "synthetic_campaigns",
    (
        ("campaign_id", "integer"),
        ("name", "text"),
        ("channel", "text"),
        ("market", "text"),
        ("start_date", "date"),
    ),
)
AD_SPEND_TABLE = Table(
    "synthetic_ad_spend",
    (
        ("spend_date", "date"),
        ("campaign_id", "integer"),
        ("impressions", "integer"),
        ("clicks", "integer"),
        ("spend", "numeric(12,2)"),
        ("currency", "text"),
    ),
)
LEADS_TABLE = Table(
    "synthetic_leads",
    (
        ("lead_id", "text"),
        ("campaign_id", "integer"),
        ("created_ts", "timestamptz"),
        ("country", "text"),
    ),
)
BOOKINGS_TABLE = Table(
    "synthetic_bookings",
    (
        ("booking_id", "text"),
        ("lead_id", "text"),
        ("booked_ts", "timestamptz"),
        ("amount", "numeric(12,2)"),
        ("currency", "text"),
    ),
)


def entities(page_size: int) -> list[Entity]:
    def fixed(rows: list[dict[str, object]]) -> Fetch:
        return lambda interval, cursor: paginate(rows, cursor, page_size)

    def per_interval(build) -> Fetch:
        def fetch(interval: Interval, cursor: int) -> Page:
            return paginate(build(interval), cursor, page_size)

        return fetch

    return [
        Entity(SOURCE, "campaigns", CAMPAIGNS_TABLE, fixed(build_campaigns())),
        Entity(SOURCE, "ad_spend", AD_SPEND_TABLE, per_interval(build_ad_spend)),
        Entity(SOURCE, "leads", LEADS_TABLE, per_interval(build_leads)),
        Entity(SOURCE, "bookings", BOOKINGS_TABLE, per_interval(build_bookings)),
    ]


def build_campaigns() -> list[dict[str, object]]:
    return [
        {
            "campaign_id": campaign_id,
            "name": name,
            "channel": channel,
            "market": market,
            "start_date": CAMPAIGNS_START.isoformat(),
        }
        for campaign_id, name, channel, market in CAMPAIGNS
    ]


def _days(interval: Interval) -> list[date]:
    """UTC days whose midnight falls in [start, end)."""
    day = interval.start.astimezone(UTC).date()
    days = []
    while (midnight := _midnight(day)) < interval.end:
        if midnight >= interval.start:
            days.append(day)
        day += timedelta(days=1)
    return days


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def build_ad_spend(interval: Interval) -> list[dict[str, object]]:
    """One row per campaign per UTC day whose midnight is in the interval."""
    rows = []
    for day in _days(interval):
        rng = random.Random(f"ad_spend:{day.isoformat()}")
        for campaign_id, _, channel, _ in CAMPAIGNS:
            low, high = SPEND_CENTS[channel]
            impressions = rng.randint(2_000, 40_000)
            rows.append(
                {
                    "spend_date": day.isoformat(),
                    "campaign_id": campaign_id,
                    "impressions": impressions,
                    "clicks": rng.randint(impressions // 200, impressions // 40),
                    "spend": f"{Decimal(rng.randint(low, high)) / 100:.2f}",
                    "currency": "EUR",
                }
            )
    return rows


def _day_leads(day: date) -> list[dict[str, object]]:
    rng = random.Random(f"leads:{day.isoformat()}")
    weights = [
        5 if channel == "search" else 3 if channel == "social" else 1
        for _, _, channel, _ in CAMPAIGNS
    ]
    leads = []
    for seq in range(1, 8 + rng.randint(0, 12) + 1):
        campaign_id, _, _, market = rng.choices(CAMPAIGNS, weights)[0]
        leads.append(
            {
                "lead_id": f"L-{day:%Y%m%d}-{seq:04d}",
                "campaign_id": campaign_id,
                "created_ts": (
                    _midnight(day) + timedelta(seconds=rng.randint(0, 86_399))
                ).isoformat(),
                "country": market,
            }
        )
    return leads


def build_leads(interval: Interval) -> list[dict[str, object]]:
    """Leads with created_ts in [start - LEADS_LOOKBACK, end), ordered by time then id."""
    since = interval.start - LEADS_LOOKBACK
    start_day = since.astimezone(UTC).date()
    end_day = interval.end.astimezone(UTC).date()
    leads = [
        lead
        for offset in range((end_day - start_day).days + 1)
        for lead in _day_leads(start_day + timedelta(days=offset))
        if since <= datetime.fromisoformat(str(lead["created_ts"])) < interval.end
    ]
    return sorted(leads, key=lambda r: (r["created_ts"], r["lead_id"]))


def _booking(lead: dict[str, object]) -> dict[str, object] | None:
    """The booking a lead becomes, if any: decided by the lead's own seed."""
    rng = random.Random(f"booking:{lead['lead_id']}")
    if rng.random() >= BOOKING_RATE:
        return None
    created = datetime.fromisoformat(str(lead["created_ts"]))
    booked = created + timedelta(
        days=rng.randint(0, MAX_BOOKING_LAG_DAYS), seconds=rng.randint(60, 7_200)
    )
    return {
        "booking_id": f"B-{str(lead['lead_id'])[2:]}",
        "lead_id": lead["lead_id"],
        "booked_ts": booked.isoformat(),
        "amount": f"{Decimal(rng.randint(150_000, 900_000)) / 100:.2f}",
        "currency": "EUR",
    }


def build_bookings(interval: Interval) -> list[dict[str, object]]:
    """Bookings with booked_ts in [start, end), from leads up to the maximum lag before it."""
    first = interval.start.astimezone(UTC).date() - timedelta(days=MAX_BOOKING_LAG_DAYS + 1)
    last = interval.end.astimezone(UTC).date()
    bookings = []
    for offset in range((last - first).days + 1):
        for lead in _day_leads(first + timedelta(days=offset)):
            booking = _booking(lead)
            if (
                booking
                and interval.start
                <= datetime.fromisoformat(str(booking["booked_ts"]))
                < interval.end
            ):
                bookings.append(booking)
    return sorted(bookings, key=lambda r: (r["booked_ts"], r["booking_id"]))
