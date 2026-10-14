"""The kept-month rule of tlc_monthly's retention (PLAN.md D35, issue #87)."""

import pytest
from pplk8s.retention import kept_months

DRIFT = ["2023-01", "2025-01", "2026-06"]


def kept(run_month, held, first_scheduled="2026-06", pinned=DRIFT, latest=3):
    return kept_months(
        run_month, held, first_scheduled=first_scheduled, pinned=pinned, latest=latest
    )


def test_a_scheduled_run_keeps_its_month_the_two_before_and_the_drift_months():
    held = ["2023-01", "2025-01", "2026-06", "2026-07", "2026-08", "2026-09"]
    assert kept("2026-10", held) == [
        "2023-01",
        "2025-01",
        "2026-06",  # a drift month, kept although it left the latest 3
        "2026-08",
        "2026-09",
        "2026-10",
    ]


def test_the_latest_months_run_across_a_year_boundary():
    held = ["2026-10", "2026-11", "2026-12"]
    assert kept("2027-01", held, first_scheduled="2026-10", pinned=[]) == [
        "2026-11",
        "2026-12",
        "2027-01",
    ]


def test_a_drift_month_inside_the_latest_3_takes_no_extra_slot():
    held = ["2023-01", "2025-01", "2026-06", "2026-07"]
    assert kept("2026-08", held) == ["2023-01", "2025-01", "2026-06", "2026-07", "2026-08"]


def test_a_backfilled_drift_month_never_retires_the_scheduled_ones():
    held = ["2025-01", "2026-06", "2026-07", "2026-08"]
    assert kept("2023-01", held) == ["2023-01", "2025-01", "2026-06", "2026-07", "2026-08"]


def test_a_month_still_loading_for_a_newer_run_counts_as_latest():
    # Catch-up: 2026-09 and 2026-10 are loading while 2026-08 runs; 2026-08 must not retire them.
    held = ["2026-07", "2026-08", "2026-09", "2026-10"]
    assert kept("2026-08", held, pinned=[]) == ["2026-08", "2026-09", "2026-10"]


def test_a_rerun_of_a_retired_month_keeps_it_for_its_own_load():
    held = ["2026-08", "2026-09", "2026-10"]
    assert kept("2026-07", held, pinned=[]) == ["2026-07", "2026-08", "2026-09", "2026-10"]


def test_an_empty_warehouse_keeps_the_run_month_and_the_pinned_ones():
    assert kept("2026-06", []) == DRIFT
    assert kept("2026-07", [], pinned=[]) == ["2026-07"]


def test_months_before_the_schedule_are_not_latest_unless_pinned():
    held = ["2024-05", "2025-01", "2026-06"]
    assert kept("2026-07", held, pinned=["2025-01"]) == ["2025-01", "2026-06", "2026-07"]


@pytest.mark.parametrize(
    ("run_month", "held", "pinned", "latest"),
    [
        ("2026-7", [], [], 3),
        ("2026-07", ["2026-13"], [], 3),
        ("2026-07", [], ["latest"], 3),
        ("2026-07", [], [], 0),
    ],
)
def test_malformed_input_is_refused(run_month, held, pinned, latest):
    with pytest.raises(ValueError):
        kept(run_month, held, pinned=pinned, latest=latest)
