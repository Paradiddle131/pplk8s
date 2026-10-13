import re
from datetime import UTC, datetime

import pytest
from airflow.sdk.exceptions import AirflowFailException
from pplk8s.context import file_event, resolve_month

RETURNS = re.compile(r"returns/(?P<day>\d{4}-\d{2}-\d{2})\.jsonl")
CONF = {"bucket": "landing", "object": "returns/2026-10-01.jsonl", "generation": "1791619920448263"}


def test_file_event_validates_and_derives_the_files_day():
    assert file_event(CONF, RETURNS) == {
        **CONF,
        "interval_start": "2026-10-01T00:00:00+00:00",
        "interval_end": "2026-10-02T00:00:00+00:00",
    }


def test_integer_generations_are_accepted_as_strings():
    assert file_event({**CONF, "generation": 17}, RETURNS)["generation"] == "17"


@pytest.mark.parametrize(
    "conf",
    [
        None,
        {},
        {**CONF, "bucket": ""},
        {**CONF, "generation": "0"},
        {**CONF, "generation": "12a"},
        {**CONF, "generation": True},
        {**CONF, "object": "returns/2026-10-01.csv"},
        {**CONF, "object": "other/returns/2026-10-01.jsonl"},
        {**CONF, "object": "returns/2026-13-01.jsonl"},
    ],
)
def test_malformed_events_fail_fast(conf):
    with pytest.raises(AirflowFailException):
        file_event(conf, RETURNS)


def test_a_scheduled_monthly_run_processes_its_data_interval():
    start, end = datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)
    assert resolve_month(start, end, end) == (start, end, "2026-08")


def test_a_december_interval_ends_in_january():
    start, end = datetime(2025, 12, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)
    assert resolve_month(start, end, end)[2] == "2025-12"


@pytest.mark.parametrize(
    ("start", "end"),
    [(None, None), ("2026-10-13T09:00:00+00:00", "2026-10-13T09:00:00+00:00")],
)
def test_a_manual_run_processes_the_last_complete_month(start, end):
    def parse(value):
        return datetime.fromisoformat(value) if value else None

    logical = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    assert resolve_month(parse(start), parse(end), logical) == (
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 10, 1, tzinfo=UTC),
        "2026-09",
    )


def test_a_manual_run_on_the_first_of_a_month_processes_the_month_before():
    logical = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert resolve_month(None, None, logical)[2] == "2025-12"


def test_a_scheduled_interval_that_is_not_one_calendar_month_fails_fast():
    start, end = datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 8, 2, tzinfo=UTC)
    with pytest.raises(AirflowFailException):
        resolve_month(start, end, end)
