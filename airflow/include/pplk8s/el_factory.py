"""EL Factory client: the only way a DAG talks to the extraction service (PLAN.md D7).

Retry ownership (PLAN.md D15): this hook never loops.
It classifies a failure and raises, and the Airflow task retry policy owns the retrying.

* Retryable (HTTP 503, any response with ``retryable: true``, connection errors, timeouts,
  5xx responses without a JSON body such as a proxy 502/504 during a rollout) raise
  :class:`ElFactoryTransientError`, an ordinary exception, so ``retries`` and exponential
  backoff on the task apply.
* Non-retryable (4xx, 502 from a rejected source request, ``retryable: false``, malformed
  responses) raise ``AirflowFailException``, which fails the task at once with no retry.
* A superseded file (409 with ``superseded: true`` from ``POST /load``) raises
  ``AirflowSkipException``: the object was overwritten, and the newer generation has its own event
  and run.

Re-running an entity from page 0 is safe because EL Factory's page 0 resets the whole
``(run_id, interval)`` of that entity, so :meth:`ElFactoryHook.extract_entity` always starts
over at page 0 and a retry never has to resume mid-pagination.

Each ``/extract`` request is time-boxed by EL Factory's ``MAX_RUN_TIME`` (PLAN.md D34): it loads
pages until the budget is spent and answers ``next_url`` for the rest, so one task attempt loops
over continuations, not single pages. ``MAX_RUN_TIME`` must stay well below
``READ_TIMEOUT_SECONDS``, because a request may overrun its budget by one page.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import requests
from airflow.providers.http.hooks.http import HttpHook
from airflow.sdk.exceptions import AirflowFailException, AirflowSkipException

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:+-]+$")
MONTH_PATTERN = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
DEFAULT_CONN_ID = "el_factory"
CONNECT_TIMEOUT_SECONDS = (
    10  # a blackholed connection (pod just replaced) should fail fast and retry
)
READ_TIMEOUT_SECONDS = 120
MAX_REQUESTS = 10_000


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
        timeout: tuple[float, float] = (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
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

    def publication(self, source: str, entity: str, month: str) -> dict[str, Any]:
        """Is a file source's data month published? (``GET /publication``, PLAN.md D34).

        Returns ``{published: True, source_uri, etag, size}`` or ``{published: False, source_uri}``.
        A CDN block is a retryable 503, so it raises :class:`ElFactoryTransientError` like any
        transient failure; it never reads as "not published".
        """
        if not MONTH_PATTERN.match(month):
            raise AirflowFailException(f"month {month!r} is not YYYY-MM")
        params = {"source": source, "entity": entity, "month": month}
        body = self._call("GET", "/publication", data=params)
        status = body.get("status") if isinstance(body, dict) else None
        if status == "not_published":
            return {"published": False, "source_uri": body.get("source_uri")}
        etag, size = (body.get("etag"), body.get("size")) if status == "published" else (None, None)
        if (
            not isinstance(etag, str)
            or not etag
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
        ):
            raise AirflowFailException(f"publication of {source}.{entity} {month}: {body!r}")
        return {"published": True, "source_uri": body.get("source_uri"), "etag": etag, "size": size}

    def extract_entity(
        self,
        source: str,
        entity: str,
        run_id: str,
        interval_start: str | datetime,
        interval_end: str | datetime,
    ) -> dict[str, Any]:
        """Extract every page of one entity; return ``{source, entity, requests, pages, rows}``."""
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
        calls = 0
        pages = 0
        rows = 0
        seen = {endpoint}
        while True:
            body = self._call("POST", endpoint, json=payload)
            response_pages, response_rows = self._validate_page(body, source, entity)
            calls += 1
            pages += response_pages
            rows += response_rows
            next_url = body["next_url"]
            if next_url is None:
                break
            endpoint = self._same_host_endpoint(next_url)
            if endpoint in seen or calls >= MAX_REQUESTS:
                raise AirflowFailException(
                    f"pagination for {source}.{entity} does not terminate at {next_url!r}"
                )
            seen.add(endpoint)
        return {
            "source": source,
            "entity": entity,
            "requests": calls,
            "pages": pages,
            "rows": rows,
        }

    def load_file(
        self, entity: str, bucket: str, name: str, generation: str | int, run_id: str
    ) -> dict[str, Any]:
        """Load one landed file at exactly ``generation``; return a compact summary."""
        if not RUN_ID_PATTERN.match(run_id):
            raise AirflowFailException(f"run_id {run_id!r} does not match {RUN_ID_PATTERN.pattern}")
        payload = {
            "entity": entity,
            "bucket": bucket,
            "object": name,
            "generation": str(generation),
            "run_id": run_id,
        }
        body = self._call("POST", "/load", json=payload)
        rows = body.get("rows") if isinstance(body, dict) else None
        if (
            not isinstance(body, dict)
            or body.get("status") != "ok"
            or not isinstance(rows, int)
            or isinstance(rows, bool)
            or rows < 0
            or body.get("generation") != str(generation)
        ):
            raise AirflowFailException(f"load {entity} returned an invalid response: {body!r}")
        return {
            "entity": entity,
            "object": body.get("object"),
            "generation": str(generation),
            "rows": rows,
        }

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
        if isinstance(body, dict) and body.get("superseded") is True:
            raise AirflowSkipException(message)
        if isinstance(body, dict) and isinstance(body.get("retryable"), bool):
            retryable = body["retryable"]
        else:
            # No EL Factory error body: the failure came from the platform (gateway, rollout).
            retryable = status in (408, 429) or status >= 500
        if retryable:
            raise ElFactoryTransientError(message)
        raise AirflowFailException(message)

    @staticmethod
    def _validate_page(body: Any, source: str, entity: str) -> tuple[int, int]:
        """Return ``(pages, rows)`` of one response; ``pages`` is 1 if EL Factory predates D34."""
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
        pages = body.get("pages", 1)
        if not isinstance(pages, int) or isinstance(pages, bool) or pages < 1:
            raise AirflowFailException(f"extract {source}.{entity} has invalid pages: {pages!r}")
        return pages, rows

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
