from datetime import UTC, datetime

from el_factory.model import Interval
from el_factory.sources.synthetic import CUSTOMER_COUNT, build_customers, build_orders


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_orders_are_byte_identical_for_the_same_interval():
    interval = Interval(utc(2026, 10, 1), utc(2026, 10, 3))

    assert build_orders(interval) == build_orders(interval)


def test_customers_are_a_fixed_snapshot_of_200_ordered_rows():
    first = build_customers()

    assert first == build_customers()
    assert len(first) == CUSTOMER_COUNT
    assert [row["customer_id"] for row in first] == list(range(1, CUSTOMER_COUNT + 1))
    assert {row["country"] for row in first} <= {"NL", "TR", "GB", "DE", "FR", "US"}
    assert all(row["signup_date"].startswith("2025-") for row in first)
    assert first[0]["email"] == "customer1@example.com"


def test_orders_exclude_the_end_boundary_and_include_the_start():
    day_one = build_orders(Interval(utc(2026, 10, 1), utc(2026, 10, 2)))
    timestamps = [row["order_ts"] for row in day_one]

    assert timestamps
    assert all("2026-10-01T" in ts for ts in timestamps)
    assert timestamps == sorted(timestamps)
    assert all(row["currency"] == "EUR" for row in day_one)


def test_splitting_an_interval_yields_the_same_orders_as_the_whole():
    whole = build_orders(Interval(utc(2026, 10, 1), utc(2026, 10, 3)))
    split = build_orders(Interval(utc(2026, 10, 1), utc(2026, 10, 2))) + build_orders(
        Interval(utc(2026, 10, 2), utc(2026, 10, 3))
    )

    assert sorted(split, key=lambda r: r["order_id"]) == sorted(whole, key=lambda r: r["order_id"])


def test_order_timestamp_exactly_at_start_is_kept_and_at_end_is_dropped():
    everything = build_orders(Interval(utc(2026, 10, 1), utc(2026, 10, 2)))
    first_ts = datetime.fromisoformat(everything[0]["order_ts"])
    last_ts = datetime.fromisoformat(everything[-1]["order_ts"])

    starting_at_first = build_orders(Interval(first_ts, utc(2026, 10, 2)))
    ending_at_last = build_orders(Interval(utc(2026, 10, 1), last_ts))

    assert starting_at_first[0]["order_id"] == everything[0]["order_id"]
    assert all(row["order_id"] != everything[-1]["order_id"] for row in ending_at_last)


def test_order_amounts_have_two_decimal_places_within_range():
    rows = build_orders(Interval(utc(2026, 10, 1), utc(2026, 10, 2)))

    for row in rows:
        assert len(row["amount"].split(".")[1]) == 2
        assert 5.0 <= float(row["amount"]) <= 500.0
        assert row["status"] in {"placed", "shipped", "cancelled"}
