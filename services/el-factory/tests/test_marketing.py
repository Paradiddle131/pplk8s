from datetime import UTC, datetime, timedelta
from decimal import Decimal

from el_factory.model import Interval
from el_factory.sources.marketing import (
    CAMPAIGNS,
    MAX_BOOKING_LAG_DAYS,
    MONTHLY_BUDGET_EUR,
    build_ad_spend,
    build_bookings,
    build_campaign_budgets,
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
    for build in (build_ad_spend, build_leads, build_bookings, build_campaign_budgets):
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


def test_a_booking_can_name_a_lead_from_an_earlier_interval():
    """Leads and bookings are extracted per interval, so a booking may name a lead created up to
    MAX_BOOKING_LAG_DAYS earlier, which a fresh warehouse has not loaded; silver keeps such a
    booking with no campaign and its lead tests warn (PLAN.md D38)."""
    leads = {lead["lead_id"] for lead in build_leads(DAY_ONE)}

    assert any(b["lead_id"] not in leads for b in build_bookings(DAY_ONE))


def test_a_campaign_budget_snapshot_is_its_month_budget_less_the_spend_so_far():
    """A balance: each day's snapshot is what is left of the month's budget after its spend."""
    october = Interval(utc(2026, 10, 1), utc(2026, 11, 1))
    snapshots = build_campaign_budgets(october)
    spend = build_ad_spend(october)
    assert len(snapshots) == 31 * len(CAMPAIGNS)
    for campaign_id, _, channel, _ in CAMPAIGNS:
        left = MONTHLY_BUDGET_EUR[channel]
        days = sorted(
            (row for row in spend if row["campaign_id"] == campaign_id),
            key=lambda r: r["spend_date"],
        )
        for day in days:
            left -= Decimal(str(day["spend"]))
            [snapshot] = [
                s
                for s in snapshots
                if s["campaign_id"] == campaign_id and s["snapshot_date"] == day["spend_date"]
            ]
            assert Decimal(snapshot["budget_eur"]) == MONTHLY_BUDGET_EUR[channel]
            assert Decimal(snapshot["remaining_eur"]) == left


def test_a_campaign_budget_starts_again_on_the_first_of_the_month():
    first = build_campaign_budgets(Interval(utc(2026, 11, 1), utc(2026, 11, 2)))
    spend = {
        r["campaign_id"]: Decimal(str(r["spend"]))
        for r in build_ad_spend(Interval(utc(2026, 11, 1), utc(2026, 11, 2)))
    }
    for campaign_id, _, channel, _ in CAMPAIGNS:
        [row] = [r for r in first if r["campaign_id"] == campaign_id]
        assert Decimal(row["remaining_eur"]) == MONTHLY_BUDGET_EUR[channel] - spend[campaign_id]
