from datetime import UTC, datetime, timedelta

from el_factory.model import Interval
from el_factory.sources.marketing import (
    CAMPAIGNS,
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
    for build in (build_ad_spend, build_leads, build_bookings):
        assert sorted(sum((build(i) for i in split), []), key=str) == sorted(
            build(TWO_DAYS), key=str
        )


def test_leads_fall_in_the_interval_and_name_a_known_campaign():
    leads = build_leads(DAY_ONE)
    campaigns = {c[0] for c in CAMPAIGNS}

    assert leads
    assert all("2026-10-01T" in str(lead["created_ts"]) for lead in leads)
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
