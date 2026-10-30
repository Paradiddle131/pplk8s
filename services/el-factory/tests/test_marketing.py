from datetime import UTC, datetime, timedelta

from el_factory.model import Interval
from el_factory.sources.marketing import (
    CAMPAIGNS,
    LEADS_LOOKBACK,
    MAX_BOOKING_LAG_DAYS,
    build_ad_spend,
    build_bookings,
    build_campaigns,
    build_leads,
)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


DAY_ONE = Interval(utc(2026, 10, 1), utc(2026, 10, 2))
TWO_DAYS = Interval(utc(2026, 10, 1), utc(2026, 10, 3))


def test_campaigns_are_a_fixed_snapshot():
    assert build_campaigns() == build_campaigns()
    assert [row["campaign_id"] for row in build_campaigns()] == [c[0] for c in CAMPAIGNS]


def test_ad_spend_has_one_row_per_campaign_per_day_in_the_interval():
    rows = build_ad_spend(TWO_DAYS)

    assert len(rows) == 2 * len(CAMPAIGNS)
    assert {row["spend_date"] for row in rows} == {"2026-10-01", "2026-10-02"}
    assert rows == build_ad_spend(TWO_DAYS)
    for row in rows:
        assert len(str(row["spend"]).split(".")[1]) == 2
        assert 0 < int(row["clicks"]) <= int(row["impressions"])


def test_ad_spend_takes_a_day_only_when_its_midnight_is_in_the_interval():
    assert build_ad_spend(Interval(utc(2026, 10, 1, 6), utc(2026, 10, 2, 6))) == build_ad_spend(
        Interval(utc(2026, 10, 2), utc(2026, 10, 3))
    )


def test_splitting_an_interval_yields_the_same_rows_as_the_whole():
    split = [
        Interval(utc(2026, 10, 1), utc(2026, 10, 2)),
        Interval(utc(2026, 10, 2), utc(2026, 10, 3)),
    ]
    for build in (build_ad_spend, build_bookings):
        assert sorted(sum((build(i) for i in split), []), key=str) == sorted(
            build(TWO_DAYS), key=str
        )
    # Leads overlap across intervals (the lookback); their union is the whole interval's leads.
    union = {str(lead): lead for i in split for lead in build_leads(i)}
    assert sorted(union, key=str) == sorted(map(str, build_leads(TWO_DAYS)))


def test_leads_reach_back_past_the_booking_lag_and_name_a_known_campaign():
    leads = build_leads(DAY_ONE)
    campaigns = {c[0] for c in CAMPAIGNS}
    created = [datetime.fromisoformat(str(lead["created_ts"])) for lead in leads]

    assert leads
    assert min(created) >= DAY_ONE.start - LEADS_LOOKBACK
    assert max(created) < DAY_ONE.end
    assert any(ts < DAY_ONE.start - timedelta(days=MAX_BOOKING_LAG_DAYS) for ts in created)
    assert all(lead["campaign_id"] in campaigns for lead in leads)
    assert [lead["created_ts"] for lead in leads] == sorted(lead["created_ts"] for lead in leads)


def test_every_booking_follows_its_lead_within_the_maximum_lag():
    month = Interval(utc(2026, 10, 1), utc(2026, 11, 1))
    leads = {
        lead["lead_id"]: lead for lead in build_leads(Interval(utc(2026, 9, 1), utc(2026, 11, 1)))
    }
    bookings = build_bookings(month)

    assert bookings
    for booking in bookings:
        created = datetime.fromisoformat(str(leads[booking["lead_id"]]["created_ts"]))
        booked = datetime.fromisoformat(str(booking["booked_ts"]))
        assert created < booked <= created + timedelta(days=MAX_BOOKING_LAG_DAYS, hours=2)
        assert month.start <= booked < month.end
        assert 1_500 <= float(str(booking["amount"])) <= 9_000


def test_a_lead_books_at_most_once():
    bookings = build_bookings(Interval(utc(2026, 9, 1), utc(2026, 11, 1)))

    assert len({b["lead_id"] for b in bookings}) == len(bookings)


def test_every_booking_of_an_interval_names_a_lead_the_same_interval_extracts():
    """A fresh warehouse holds only the leads of the intervals it extracted, so a booking must never
    point at a lead the same interval's leads extract leaves out (the first lab run of
    marketing_elt failed slv_bookings' lead tests on exactly this)."""
    for interval in (DAY_ONE, Interval(utc(2026, 9, 30), utc(2026, 10, 1))):
        leads = {lead["lead_id"] for lead in build_leads(interval)}
        bookings = build_bookings(interval)

        assert bookings
        assert [b["booking_id"] for b in bookings if b["lead_id"] not in leads] == []
