"""Minimal Airflow 3 REST client: trigger one DAG run and classify the answer for ack/nack."""

from __future__ import annotations

import enum
import logging

import requests

log = logging.getLogger(__name__)


class Outcome(enum.Enum):
    TRIGGERED = "triggered"  # 200: a new run exists -> ack
    DUPLICATE = "duplicate"  # 409: the run id exists, this is a redelivery -> ack
    REJECTED = "rejected"  # other 4xx: the request itself is wrong, retrying cannot help -> ack
    RETRY = "retry"  # 5xx, 404, network: Airflow or the DAG is not ready -> nack, redeliver


class AirflowClient:
    def __init__(self, base_url: str, username: str, password: str, timeout: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._timeout = timeout
        self._session = requests.Session()
        self._token: str | None = None

    def trigger(self, dag_id: str, run_id: str, conf: dict[str, str]) -> tuple[Outcome, str]:
        body = {"dag_run_id": run_id, "logical_date": None, "conf": conf}
        try:
            response = self._post(f"/api/v2/dags/{dag_id}/dagRuns", body)
            if response.status_code == 401:  # the JWT expired: get a new one, try once more
                self._token = None
                response = self._post(f"/api/v2/dags/{dag_id}/dagRuns", body)
        except requests.RequestException as exc:
            return Outcome.RETRY, f"request failed: {exc}"
        status = response.status_code
        detail = f"HTTP {status}: {response.text[:300]}"
        if 200 <= status < 300:
            return Outcome.TRIGGERED, detail
        if status == 409:
            return Outcome.DUPLICATE, detail
        # 404: the DAG is unknown or stale (not parsed yet, or its file vanished); that heals, so
        # keep the event instead of dropping it.  408/429 are throttling.
        if status in (404, 408, 429) or status >= 500:
            return Outcome.RETRY, detail
        return Outcome.REJECTED, detail

    def _post(self, path: str, body: dict) -> requests.Response:
        return self._session.post(
            self._base + path,
            json=body,
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=self._timeout,
        )

    def _get_token(self) -> str:
        if self._token is None:
            response = self._session.post(
                f"{self._base}/auth/token",
                json={"username": self._username, "password": self._password},
                timeout=self._timeout,
            )
            response.raise_for_status()
            self._token = response.json()["access_token"]
        return self._token
