from datetime import UTC, datetime

import pytest
import requests

BODY = {
    "source": "open_meteo",
    "entity": "hourly_weather",
    "run_id": "weather__1",
    "interval_start": "2026-09-01T00:00:00+00:00",
    "interval_end": "2026-09-01T03:00:00+00:00",
}

PAYLOAD = {
    "hourly": {
        "time": [
            "2026-08-31T23:00",
            "2026-09-01T00:00",
            "2026-09-01T01:00",
            "2026-09-01T02:00",
            "2026-09-01T03:00",
        ],
        "temperature_2m": [14.0, 12.5, None, 11.25, 10.0],
        "precipitation": [0.0, 0.1, 0.0, 0.4, 0.0],
    }
}


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


@pytest.fixture
def archive(monkeypatch):
    calls = []

    def install(response: FakeResponse):
        def fake_get(url, params=None, timeout=None):
            calls.append({"url": url, "params": params, "timeout": timeout})
            return response

        monkeypatch.setattr(requests, "get", fake_get)
        return calls

    return install


def test_parses_hours_inside_the_interval_only(make_client, warehouse, archive):
    calls = archive(FakeResponse(200, PAYLOAD))
    client = make_client()

    response = client.post("/extract", json=BODY).get_json()

    assert response["status"] == "ok"
    assert response["rows"] == 3
    assert response["next_url"] == "/extract?cursor=1"
    loaded = next(iter(warehouse.tables["open_meteo_hourly_weather"].values()))
    assert [row["observed_at"] for row in loaded] == [
        datetime(2026, 9, 1, 0, tzinfo=UTC).isoformat(),
        datetime(2026, 9, 1, 1, tzinfo=UTC).isoformat(),
        datetime(2026, 9, 1, 2, tzinfo=UTC).isoformat(),
    ]
    assert loaded[0]["location"] == "Amsterdam"
    assert loaded[1]["temperature_c"] is None
    assert calls[0]["url"] == "http://open-meteo.test/v1/archive"
    assert calls[0]["params"]["start_date"] == "2026-09-01"
    assert calls[0]["params"]["end_date"] == "2026-09-01"
    assert calls[0]["params"]["hourly"] == "temperature_2m,precipitation"
    assert calls[0]["params"]["timezone"] == "UTC"
    assert calls[0]["timeout"] == 10


def test_pages_walk_the_fixed_locations(make_client, archive):
    archive(FakeResponse(200, PAYLOAD))
    client = make_client()
    body = {**BODY, "cursor": "2"}

    response = client.post("/extract", json=body).get_json()

    assert response["page"] == 2
    assert response["next_url"] is None


def test_upstream_server_error_is_a_retryable_503(make_client, archive):
    archive(FakeResponse(502))

    response = make_client().post("/extract", json=BODY)

    assert response.status_code == 503
    assert response.get_json()["retryable"] is True


def test_upstream_client_error_is_a_non_retryable_502(make_client, archive):
    archive(FakeResponse(400))

    response = make_client().post("/extract", json=BODY)

    assert response.status_code == 502
    assert response.get_json()["retryable"] is False


def test_upstream_connection_failure_is_a_retryable_503(make_client, monkeypatch):
    def refuse(url, params=None, timeout=None):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(requests, "get", refuse)

    response = make_client().post("/extract", json=BODY)

    assert response.status_code == 503
    assert response.get_json()["retryable"] is True


def test_missing_hourly_block_is_a_retryable_503(make_client, archive):
    archive(FakeResponse(200, {"error": True}))

    response = make_client().post("/extract", json=BODY)

    assert response.status_code == 503
