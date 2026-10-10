import re

import pytest
from airflow.sdk.exceptions import AirflowFailException
from pplk8s.context import file_event

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
