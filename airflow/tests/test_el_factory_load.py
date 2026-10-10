import json

import pytest
import responses
from airflow.sdk.exceptions import AirflowFailException, AirflowSkipException
from pplk8s.el_factory import ElFactoryHook, ElFactoryTransientError

BASE = "http://el-factory.test:80"
RUN_ID = "gcs__landing__returns_2026-10-01.jsonl__17"
ARGS = ("partner_returns", "landing", "returns/2026-10-01.jsonl", "17", RUN_ID)


def ok(rows=3, generation="17"):
    return {
        "status": "ok",
        "entity": "partner_returns",
        "object": "gs://landing/returns/2026-10-01.jsonl",
        "generation": generation,
        "rows": rows,
    }


@responses.activate
def test_load_file_posts_the_exact_generation_and_returns_a_summary():
    responses.post(f"{BASE}/load", json=ok())

    summary = ElFactoryHook().load_file(*ARGS)

    assert summary == {
        "entity": "partner_returns",
        "object": "gs://landing/returns/2026-10-01.jsonl",
        "generation": "17",
        "rows": 3,
    }
    assert json.loads(responses.calls[0].request.body) == {
        "entity": "partner_returns",
        "bucket": "landing",
        "object": "returns/2026-10-01.jsonl",
        "generation": "17",
        "run_id": RUN_ID,
    }


@responses.activate
def test_a_superseded_generation_skips_the_task():
    responses.post(
        f"{BASE}/load",
        status=409,
        json={"status": "error", "retryable": False, "superseded": True, "error": "gone"},
    )
    with pytest.raises(AirflowSkipException):
        ElFactoryHook().load_file(*ARGS)


@responses.activate
@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (422, {"status": "error", "retryable": False, "error": "bad line"}, AirflowFailException),
        (409, {"status": "error", "retryable": False, "error": "other"}, AirflowFailException),
        (503, {"status": "error", "retryable": True, "error": "busy"}, ElFactoryTransientError),
    ],
)
def test_load_errors_follow_the_retry_contract(status, body, error):
    responses.post(f"{BASE}/load", status=status, json=body)
    with pytest.raises(error):
        ElFactoryHook().load_file(*ARGS)


@responses.activate
@pytest.mark.parametrize(
    "body",
    [ok(rows=-1), ok(rows=True), ok(generation="18"), {"status": "ok"}, ["not", "a", "dict"]],
)
def test_invalid_load_responses_fail_fast(body):
    responses.post(f"{BASE}/load", json=body)
    with pytest.raises(AirflowFailException):
        ElFactoryHook().load_file(*ARGS)


def test_unsafe_run_ids_are_rejected_before_any_call():
    with pytest.raises(AirflowFailException):
        ElFactoryHook().load_file("partner_returns", "landing", "x", "1", "bad id")
