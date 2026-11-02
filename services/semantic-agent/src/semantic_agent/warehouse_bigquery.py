"""The warehouse seam on BigQuery, the lab project (AGENT_WAREHOUSE=bigquery; SL-13, SL-19).

The same two tables as on Postgres, in the `ops` dataset that `dbt run-operation agent_warehouse`
creates, held to the lab's $0.00 rule (platform/gcp/README.md):
- the audit row goes in by a parameterised DML `INSERT`, never a streaming insert (`insertAll` has
  no free tier); `called_at` is the job's `CURRENT_TIMESTAMP()`, since the table has no column
  default (the emulator refuses one, SL-7);
- every job is capped at `BQ_MAXIMUM_BYTES_BILLED` bytes (default 1 GiB, free-path.yaml's
  `caps.bigquery_maximum_bytes_billed`, as dbt's `gcp` output) and carries job labels naming the
  agent, the session and what the job is for, so the Data Access audit log and
  `INFORMATION_SCHEMA.JOBS` join to the audit rows (docs/semantic-layer-on-bigquery.md);
- `AUDIT_SERVICE_ACCOUNT`, when set, is the identity the audit insert runs as, by impersonation
  from the agent's own credentials (SL-10: only `agent-audit` writes the audit table); unset, the
  audit runs as the agent's own credentials.

Env: `GCP_PROJECT` (required); `BQ_API_ENDPOINT` for the BigQuery emulator (`make
bigquery-emulator-check`, no credentials, so no impersonation); else application default
credentials, or the access token in `GCP_ACCESS_TOKEN` where a proxy injects the real one (cloud
sessions), as tests/e2e/lib/bigquery_target.py.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from functools import cache
from typing import Any

import requests
from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import GoogleAuthError
from google.cloud import bigquery
from google.cloud.bigquery.retry import DEFAULT_JOB_RETRY, DEFAULT_RETRY

from semantic_agent.warehouse import Readiness, WarehouseError, reason

DATASET = "ops"
LOCATION = "US"  # the lab's datasets, where the free tiers meet (SL-13)
# platform/gcp/free-path.yaml caps.bigquery_maximum_bytes_billed, as dbt's `gcp` output.
DEFAULT_MAXIMUM_BYTES_BILLED = 1073741824
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
# One audit row or one ledger read per data call: a few seconds when BigQuery answers, and a bounded
# wait when it does not (the client's defaults retry for ten minutes), after which the audit
# withholds the result and the freshness says it is unknown.
RETRY = DEFAULT_RETRY.with_deadline(30)
JOB_RETRY = DEFAULT_JOB_RETRY.with_deadline(60)
TIMEOUT = 30

AUDIT_SQL = """
insert into `{table}` (
  called_at, agent, tool, user_id, session_id, invocation_id, call_id,
  metrics, filters, arguments, sql, rows_returned, freshness, error
) values (
  current_timestamp(), @agent, @tool, @user_id, @session_id, @invocation_id, @call_id,
  @metrics, parse_json(@filters), parse_json(@arguments), @sql, @rows_returned, @freshness, @error
)
"""

# max_age is an INTERVAL, which the client returns as a dateutil relativedelta; in seconds it reads
# back as the timedelta the Postgres implementation returns.
READINESS_SQL = """
with asked as (
  select product from unnest(@products) as product
),
ready as (
  select product, max(interval_end) as ready_until
  from `{readiness}`
  where status = 'ready' and product in unnest(@products)
  group by product
)
select asked.product,
       ready.ready_until,
       timestamp_diff(
         timestamp '1970-01-01 00:00:00+00' + coalesce(own.max_age, pipeline.max_age),
         timestamp '1970-01-01 00:00:00+00', second) as max_age_seconds
from asked
left join ready on ready.product = asked.product
left join `{deadlines}` own on own.product = asked.product
left join `{deadlines}` pipeline on pipeline.product = split(asked.product, '.')[offset(0)]
order by asked.product
"""

# What the client, its transport and its credentials raise when BigQuery cannot be reached or
# refuses a job; mapped to WarehouseError.
ERRORS = (GoogleAPIError, GoogleAuthError, requests.RequestException, OSError)


def project() -> str:
    if not (value := os.environ.get("GCP_PROJECT")):
        raise WarehouseError("GCP_PROJECT is unset: the BigQuery warehouse needs the project's id")
    return value


def maximum_bytes_billed() -> int:
    return int(os.environ.get("BQ_MAXIMUM_BYTES_BILLED", DEFAULT_MAXIMUM_BYTES_BILLED))


def label(value: str) -> str:
    """A job label value by BigQuery's rules: at most 63 lowercase letters, digits, `_` and `-`."""
    return re.sub(r"[^a-z0-9_-]", "_", value.lower())[:63]


def job_labels(purpose: str, agent: str | None, session_id: str | None) -> dict[str, str]:
    labels = {"component": "semantic-agent", "purpose": purpose}
    if agent:
        labels["agent"] = label(agent)
    if session_id:
        labels["session"] = label(session_id)
    return labels


@cache
def client(project_id: str, endpoint: str, token: str, impersonate: str) -> bigquery.Client:
    """One client per configuration, built on first use; `impersonate` names the service account
    its jobs run as (empty: the caller's own credentials)."""
    if endpoint:
        if impersonate:
            raise WarehouseError(
                "AUDIT_SERVICE_ACCOUNT needs real BigQuery: the emulator takes no credentials"
            )
        from google.api_core.client_options import ClientOptions
        from google.auth.credentials import AnonymousCredentials

        return bigquery.Client(
            project=project_id,
            credentials=AnonymousCredentials(),
            client_options=ClientOptions(api_endpoint=endpoint),
        )
    if token:
        import google.oauth2.credentials

        credentials = google.oauth2.credentials.Credentials(token)
    else:
        import google.auth

        credentials, _ = google.auth.default(scopes=SCOPES)
    if impersonate:
        from google.auth import impersonated_credentials

        credentials = impersonated_credentials.Credentials(
            source_credentials=credentials, target_principal=impersonate, target_scopes=SCOPES
        )
    return bigquery.Client(project=project_id, credentials=credentials, location=LOCATION)


def _client(impersonate: str = "") -> bigquery.Client:
    env = os.environ.get
    return client(project(), env("BQ_API_ENDPOINT", ""), env("GCP_ACCESS_TOKEN", ""), impersonate)


def audit_params(row: dict[str, Any]) -> list[Any]:
    """The audit row as the insert's parameters: the JSON columns as JSON text for parse_json, the
    metrics as an array (BigQuery stores no NULL array: none is an empty one)."""
    metrics = row["metrics"]
    if metrics is None:
        metrics = []
    elif not isinstance(metrics, list):
        metrics = [metrics]

    def text(name: str) -> bigquery.ScalarQueryParameter:
        return bigquery.ScalarQueryParameter(name, "STRING", row[name])

    def as_json(value: Any) -> str | None:
        return None if value is None else json.dumps(value, default=str)

    return [
        *(text(n) for n in ("agent", "tool", "user_id", "session_id", "invocation_id", "call_id")),
        bigquery.ArrayQueryParameter("metrics", "STRING", [str(m) for m in metrics]),
        bigquery.ScalarQueryParameter("filters", "STRING", as_json(row["filters"])),
        bigquery.ScalarQueryParameter("arguments", "STRING", as_json(row["arguments"])),
        text("sql"),
        bigquery.ScalarQueryParameter("rows_returned", "INT64", row["rows_returned"]),
        text("freshness"),
        text("error"),
    ]


class BigQueryWarehouse:
    def _run(
        self,
        bq: bigquery.Client,
        sql: str,
        params: list[Any],
        labels: dict[str, str],
    ) -> list[bigquery.Row]:
        config = bigquery.QueryJobConfig(
            query_parameters=params,
            maximum_bytes_billed=maximum_bytes_billed(),
            labels=labels,
        )
        job = bq.query(sql, job_config=config, timeout=TIMEOUT, retry=RETRY, job_retry=JOB_RETRY)
        return list(job.result(timeout=TIMEOUT, retry=RETRY, job_retry=JOB_RETRY))

    def insert_audit(self, row: dict[str, Any]) -> None:
        try:
            bq = _client(os.environ.get("AUDIT_SERVICE_ACCOUNT", ""))
            table = f"{bq.project}.{DATASET}.agent_queries"
            labels = job_labels("audit", row.get("agent"), row.get("session_id"))
            self._run(bq, AUDIT_SQL.format(table=table), audit_params(row), labels)
        except ERRORS as e:
            raise WarehouseError(reason(e)) from e

    def readiness(
        self, products: list[str], *, agent: str | None = None, session_id: str | None = None
    ) -> list[Readiness]:
        try:
            bq = _client()
            sql = READINESS_SQL.format(
                readiness=f"{bq.project}.{DATASET}.readiness",
                deadlines=f"{bq.project}.{DATASET}.product_deadlines",
            )
            params = [bigquery.ArrayQueryParameter("products", "STRING", products)]
            rows = self._run(bq, sql, params, job_labels("freshness", agent, session_id))
        except ERRORS as e:
            raise WarehouseError(reason(e)) from e
        return [
            (
                product,
                ready_until,
                datetime.timedelta(seconds=seconds) if seconds is not None else None,
            )
            for product, ready_until, seconds in rows
        ]


def warehouse() -> BigQueryWarehouse:
    return BigQueryWarehouse()
