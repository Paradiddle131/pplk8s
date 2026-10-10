from datetime import UTC, datetime, timedelta

from pplk8s.context import resolve_interval, safe_run_id
from pplk8s.el_factory import RUN_ID_PATTERN


def test_airflow_run_ids_match_el_factory_pattern():
    for run_id in (
        "manual__2026-10-09T10:15:30.123456+00:00",
        "scheduled__2026-10-08T00:00:00+00:00",
        "asset_triggered__2026-10-09T00:00:00+00:00",
    ):
        assert RUN_ID_PATTERN.match(run_id)
        assert safe_run_id(run_id) == run_id


def test_unsafe_run_id_is_sanitized_deterministically():
    assert safe_run_id("manual run/1 é") == "manual_run_1__"
    assert RUN_ID_PATTERN.match(safe_run_id("manual run/1 é"))


def test_scheduled_interval_is_kept():
    start, end = datetime(2026, 10, 8, tzinfo=UTC), datetime(2026, 10, 9, tzinfo=UTC)
    assert resolve_interval(start, end, end) == (start, end)


def test_empty_manual_interval_falls_back_to_previous_utc_day():
    logical = datetime(2026, 10, 9, 10, 30, tzinfo=UTC)
    start, end = resolve_interval(logical, logical, logical)
    assert end == datetime(2026, 10, 9, tzinfo=UTC)
    assert end - start == timedelta(days=1)
    assert resolve_interval(None, None, logical) == (start, end)
