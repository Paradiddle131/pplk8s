from dataclasses import dataclass, field

import pytest
import requests
import responses

from event_adapter.airflow import AirflowClient, Outcome
from event_adapter.main import handle
from event_adapter.routing import Route

ROUTES = [Route("landing", "returns/", "returns_file_arrival")]
BASE = "http://airflow.test:8080"
ATTRS = {
    "eventType": "OBJECT_FINALIZE",
    "bucketId": "landing",
    "objectId": "returns/2026-10-01.jsonl",
    "objectGeneration": "17",
}


@dataclass
class FakeMessage:
    attributes: dict
    message_id: str = "m-1"
    acked: list = field(default_factory=list)

    def ack(self):
        self.acked.append("ack")

    def nack(self):
        self.acked.append("nack")


class FakeAirflow:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def trigger(self, dag_id, run_id, conf):
        self.calls.append((dag_id, run_id, conf))
        return self.outcome, "detail"


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (Outcome.TRIGGERED, "ack"),
        (Outcome.DUPLICATE, "ack"),
        (Outcome.REJECTED, "ack"),
        (Outcome.RETRY, "nack"),
    ],
)
def test_ack_rule(outcome, expected):
    message = FakeMessage(dict(ATTRS))

    handle(message, ROUTES, FakeAirflow(outcome))

    assert message.acked == [expected]


def test_ignored_events_are_acked_without_calling_airflow():
    message = FakeMessage({**ATTRS, "objectId": "elsewhere/x"})
    airflow = FakeAirflow(Outcome.TRIGGERED)

    assert handle(message, ROUTES, airflow) == "ignored"
    assert message.acked == ["ack"]
    assert airflow.calls == []


def token():
    responses.post(f"{BASE}/auth/token", json={"access_token": "jwt-1"})


@responses.activate
@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (200, Outcome.TRIGGERED),
        (409, Outcome.DUPLICATE),
        (400, Outcome.REJECTED),
        (422, Outcome.REJECTED),
        (404, Outcome.RETRY),
        (429, Outcome.RETRY),
        (500, Outcome.RETRY),
        (503, Outcome.RETRY),
    ],
)
def test_airflow_statuses_map_to_outcomes(status, outcome):
    token()
    responses.post(f"{BASE}/api/v2/dags/d/dagRuns", status=status, json={})

    assert AirflowClient(BASE, "u", "p").trigger("d", "r", {})[0] is outcome


@responses.activate
def test_trigger_sends_the_run_id_conf_and_no_logical_date():
    token()
    responses.post(f"{BASE}/api/v2/dags/d/dagRuns", json={})

    AirflowClient(BASE, "u", "p").trigger("d", "run-1", {"bucket": "landing"})

    request = responses.calls[1].request
    assert request.headers["Authorization"] == "Bearer jwt-1"
    assert (
        request.body
        == b'{"dag_run_id": "run-1", "logical_date": null, "conf": {"bucket": "landing"}}'
    )


@responses.activate
def test_an_expired_token_is_refreshed_once():
    responses.post(f"{BASE}/auth/token", json={"access_token": "old"})
    responses.post(f"{BASE}/auth/token", json={"access_token": "new"})
    responses.post(f"{BASE}/api/v2/dags/d/dagRuns", status=401, json={})
    responses.post(f"{BASE}/api/v2/dags/d/dagRuns", json={})
    client = AirflowClient(BASE, "u", "p")

    assert client.trigger("d", "r", {})[0] is Outcome.TRIGGERED
    assert responses.calls[3].request.headers["Authorization"] == "Bearer new"


@responses.activate
def test_network_and_login_failures_are_retried():
    responses.post(f"{BASE}/auth/token", body=requests.ConnectionError("refused"))
    assert AirflowClient(BASE, "u", "p").trigger("d", "r", {})[0] is Outcome.RETRY
    responses.replace(responses.POST, f"{BASE}/auth/token", status=503)
    assert AirflowClient(BASE, "u", "p").trigger("d", "r", {})[0] is Outcome.RETRY
