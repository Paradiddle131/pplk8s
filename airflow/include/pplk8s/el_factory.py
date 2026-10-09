"""EL Factory client: the only way a DAG talks to the extraction service (PLAN.md D7).

Retry ownership (PLAN.md D15): this hook never loops.
It classifies a failure and raises, and the Airflow task retry policy owns the retrying.

* Retryable (HTTP 503, any response with ``retryable: true``, connection errors, timeouts,
  5xx responses without a JSON body such as a proxy 502/504 during a rollout) raise
  :class:`ElFactoryTransientError`, an ordinary exception, so ``retries`` and exponential
  backoff on the task apply.
* Non-retryable (4xx, 502 from a rejected source request, ``retryable: false``, malformed
  responses) raise ``AirflowFailException``, which fails the task at once with no retry.

Re-running an entity from page 0 is safe because EL Factory's page 0 resets the whole
``(run_id, interval)`` of that entity, so :meth:`ElFactoryHook.extract_entity` always starts
over at page 0 and a retry never has to resume mid-pagination.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import requests
from airflow.exceptions import AirflowFailException
from airflow.providers.http.hooks.http import HttpHook

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:+-]+$")
DEFAULT_CONN_ID = "el_factory"
DEFAULT_TIMEOUT_SECONDS = 120
MAX_PAGES = 10_000


class ElFactoryTransientError(Exception):
    """A retryable EL Factory or network failure; Airflow's task retry handles it."""


class ElFactoryHook(HttpHook):
    """Typed client for the EL Factory HTTP contract (services/el-factory/README.md)."""

    conn_name_attr = "http_conn_id"
    default_conn_name = DEFAULT_CONN_ID
    conn_type = "http"
    hook_name = "EL Factory"

    def __init__(
        self,
        http_conn_id: str = DEFAULT_CONN_ID,
        *,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        super().__init__(http_conn_id=http_conn_id)
        self.timeout = timeout

    def get_catalog(self, pipeline: str) -> list[dict[str, str]]:
        """Return the enabled ``[{source, entity}]`` pairs of ``pipeline``."""
        body = self._call("GET", "/catalog", data={"pipeline": pipeline})
        if not isinstance(body, list):
            raise AirflowFailException(f"catalog for {pipeline!r} is not a list: {body!r}")
        entries: list[dict[str, str]] = []
        for item in body:
            if not (
                isinstance(item, dict)
                and isinstance(item.get("source"), str)
                and isinstance(item.get("entity"), str)
            ):
                raise AirflowFailException(f"malformed catalog entry: {item!r}")
            entries.append({"source": item["source"], "entity": item["entity"]})
        return entries

    def extract_entity(
        self,
        source: str,
        entity: str,
        run_id: str,
        interval_start: str | datetime,
        interval_end: str | datetime,
    ) -> dict[str, Any]:
        """Extract every page of one entity and return ``{source, entity, pages, rows}``."""
        if not RUN_ID_PATTERN.match(run_id):
            raise AirflowFailException(f"run_id {run_id!r} does not match {RUN_ID_PATTERN.pattern}")
        payload = {
            "source": source,
            "entity": entity,
            "run_id": run_id,
            "interval_start": _iso(interval_start),
            "interval_end": _iso(interval_end),
        }
        endpoint = "/extract"
        pages = 0
        rows = 0
        seen = {endpoint}
        while True:
            body = self._call("POST", endpoint, json=payload)
            page_rows = self._validate_page(body, source, entity)
            pages += 1
            rows += page_rows
            next_url = body["next_url"]
            if next_url is None:
                break
            endpoint = self._same_host_endpoint(next_url)
            if endpoint in seen or pages >= MAX_PAGES:
                raise AirflowFailException(
                    f"pagination for {source}.{entity} does not terminate at {next_url!r}"
                )
            seen.add(endpoint)
        return {"source": source, "entity": entity, "pages": pages, "rows": rows}

    def _call(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        self.method = method
        try:
            response = self.run(
                endpoint,
                extra_options={"check_response": False, "timeout": self.timeout},
                **kwargs,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise ElFactoryTransientError(f"{method} {endpoint}: {exc}") from exc
        return self._parse(method, endpoint, response)

    @staticmethod
    def _parse(method: str, endpoint: str, response: requests.Response) -> Any:
        status = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = None
        if 200 <= status < 300:
            if body is None:
                raise AirflowFailException(f"{method} {endpoint}: {status} without a JSON body")
            return body
        detail = body.get("error") if isinstance(body, dict) else response.text[:200]
        message = f"{method} {endpoint}: HTTP {status}: {detail}"
        if isinstance(body, dict) and isinstance(body.get("retryable"), bool):
            retryable = body["retryable"]
        else:
            # No EL Factory error body: the failure came from the platform (gateway, rollout).
            retryable = status in (408, 429) or status >= 500
        if retryable:
            raise ElFactoryTransientError(message)
        raise AirflowFailException(message)

    @staticmethod
    def _validate_page(body: Any, source: str, entity: str) -> int:
        if not isinstance(body, dict):
            raise AirflowFailException(f"extract response is not an object: {body!r}")
        if body.get("status") != "ok":
            raise AirflowFailException(f"extract {source}.{entity} status is not ok: {body!r}")
        rows = body.get("rows")
        if not isinstance(rows, int) or isinstance(rows, bool) or rows < 0:
            raise AirflowFailException(f"extract {source}.{entity} has invalid rows: {rows!r}")
        if "next_url" not in body or not (
            body["next_url"] is None or isinstance(body["next_url"], str)
        ):
            raise AirflowFailException(f"extract {source}.{entity} has invalid next_url: {body!r}")
        return rows

    def _same_host_endpoint(self, next_url: str) -> str:
        """Return ``next_url`` as a path+query, refusing any other host."""
        parts = urlsplit(next_url)
        if parts.scheme or parts.netloc:
            base = urlsplit(self.url_from_endpoint(""))
            if (parts.scheme, parts.netloc) != (base.scheme, base.netloc):
                raise AirflowFailException(f"next_url {next_url!r} points to a different host")
        if not parts.path.startswith("/"):
            raise AirflowFailException(f"next_url {next_url!r} is not an absolute path")
        return parts.path + (f"?{parts.query}" if parts.query else "")


def _iso(value: str | datetime) -> str:
    return value.isoformat() if isinstance(value, datetime) else value
