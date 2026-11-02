"""The warehouse seam on BigQuery, the lab project (ELF_WAREHOUSE=bigquery; SL-19, #227).

The same ds_source tables and the same idempotence as on Postgres (warehouse_postgres.py), held to
the lab's $0.00 rule (platform/gcp/README.md):
- rows go in by a load job, which is free, never by a streaming insert (`insertAll` has no free
  tier): the page's or file's rows, with their metadata columns, are uploaded as NDJSON into a
  staging table of their own;
- one multi-statement transaction then replaces the load's scope in the landing table and copies
  the staged rows in, stamping `_loaded_at`, so a reload never duplicates rows and a reader never
  sees the scope half replaced, as Postgres's one transaction does: a page 0 clears its whole
  (run, interval), any other page only itself, and a file every row of its object. Two concurrent
  loads of the same scope cannot interleave either: BigQuery aborts one transaction ("concurrent
  update"), which is transient, so the caller's retry redoes it. The transaction's DML bills
  bytes from the free 1 TiB of queries a month, a few tens of MB per load on these small tables;
- every query job is capped at `maximum_bytes_billed` (free-path.yaml's
  `caps.bigquery_maximum_bytes_billed`, 1 GiB, as dbt's `gcp` output) and every job carries labels
  naming EL Factory, what it is for, the table and the run, so `INFORMATION_SCHEMA.JOBS` shows what
  each load cost.
The file sources (TLC) never land here: BigQuery keeps no `FileLedger`, so the app serves none.

Credentials as the agent's (services/semantic-agent/src/semantic_agent/warehouse_bigquery.py):
`BQ_API_ENDPOINT` for the BigQuery emulator (no credentials); else the access token in
`GCP_ACCESS_TOKEN` where a proxy injects the real one (cloud sessions), else application default
credentials (Cloud Run's service account). The project is `GCP_PROJECT`.
"""

from __future__ import annotations

import io
import json
import logging
import re
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import TYPE_CHECKING, Any

import requests
from google.api_core import exceptions as api_exceptions
from google.api_core.exceptions import GoogleAPIError
from google.auth import exceptions as auth_exceptions
from google.cloud import bigquery
from google.cloud.bigquery.retry import DEFAULT_JOB_RETRY, DEFAULT_RETRY

from el_factory.model import Table
from el_factory.warehouse import FileLoad, PageLoad, WarehouseError

if TYPE_CHECKING:
    from el_factory.config import Config

log = logging.getLogger(__name__)

DATASET = "ds_source"
LOCATION = "US"  # the lab's datasets, where the free tiers meet (SL-13)
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
# A load is a few seconds when BigQuery answers; past these the request fails as transient and the
# caller's retry redoes it (the client's defaults would retry for ten minutes, past the caller's
# 120 s read timeout).
RETRY = DEFAULT_RETRY.with_deadline(60)
JOB_RETRY = DEFAULT_JOB_RETRY.with_deadline(90)
TIMEOUT = 60
# A staging table outlives its load only if EL Factory dies between the load and the drop.
STAGING_TTL = timedelta(hours=1)

# Postgres column types of the sources' tables (model.Table) as BigQuery's.
TYPES = {
    "text": "STRING",
    "integer": "INT64",
    "bigint": "INT64",
    "double precision": "FLOAT64",
    "boolean": "BOOL",
    "date": "DATE",
    "timestamptz": "TIMESTAMP",
}
NUMERIC = re.compile(r"numeric\(\d+,\s*\d\)")  # a scale up to 9 fits BigQuery's NUMERIC

PAGE_METADATA = (
    bigquery.SchemaField("_run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("_interval_start", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("_interval_end", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("_page", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("_source_uri", "STRING", mode="REQUIRED"),
    # Postgres's DEFAULT now(): every insert below sets it, since the emulator refuses a column
    # default (semantic/PLAN.md SL-7).
    bigquery.SchemaField("_loaded_at", "TIMESTAMP"),
)
FILE_METADATA = (
    bigquery.SchemaField("_run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("_source_uri", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("_generation", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("_loaded_at", "TIMESTAMP"),
)

# Where a page's scope is: page 0 starts a (re)load of the whole (run, interval), clearing every
# page, so a re-run that yields fewer pages leaves none behind; any other page replaces only itself.
PAGE_SCOPE = (
    "_run_id = @run_id and _interval_start = @interval_start and _interval_end = @interval_end"
)
# The staged rows carry their metadata columns, so the copy selects no parameter, and both
# statements filter by the same scope: the BigQuery emulator hands every statement of a script all
# of the job's parameters, so a statement that leaves one out fails there, and a parameter in an
# INSERT's select list binds wrong (SL-7). The staged rows all lie in the scope by construction.
REPLACE = """begin transaction;
delete from `{table}` where {scope};
insert into `{table}` ({columns}, _loaded_at)
select {columns}, current_timestamp() from `{staging}`
where {scope}{guard};
commit transaction;"""
# A file replaces every row of its object, unless a newer generation is already loaded: then the
# delete matches nothing and the insert copies nothing, so a newer load that commits first wins.
NEWER = (
    "select 1 from `{table}` where _source_uri = @source_uri and _generation > @generation limit 1"
)
FILE_SCOPE = "_source_uri = @source_uri and _generation <= @generation"

# What the client, its transport and its credentials raise when BigQuery cannot be reached or
# refuses a job; mapped to WarehouseError.
ERRORS = (GoogleAPIError, auth_exceptions.GoogleAuthError, requests.RequestException, OSError)
TRANSIENT = (
    api_exceptions.ServerError,
    api_exceptions.TooManyRequests,
    api_exceptions.RetryError,
    auth_exceptions.TransportError,
    requests.ConnectionError,
    requests.Timeout,
    ConnectionError,
    TimeoutError,
)
# A transaction BigQuery aborted for a concurrent one on the same table, and quota or rate refusals
# (403 rateLimitExceeded): a retry can succeed.
TRANSIENT_MESSAGE = re.compile(
    r"concurrent update|could not serialize|rateLimitExceeded|quotaExceeded|jobRateLimitExceeded",
    re.IGNORECASE,
)


def from_config(config: Config) -> BigQueryWarehouse:
    endpoint, token = config.bigquery_endpoint or "", config.gcp_access_token or ""
    return BigQueryWarehouse(
        lambda: client(config.gcp_project, endpoint, token),
        maximum_bytes_billed=config.bigquery_maximum_bytes_billed,
    )


@cache
def client(project_id: str, endpoint: str, token: str) -> bigquery.Client:
    """One client per configuration, built on first use, so the app starts without BigQuery."""
    if endpoint:
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
    return bigquery.Client(project=project_id, credentials=credentials, location=LOCATION)


def schema_of(table: Table, metadata: Sequence[bigquery.SchemaField]) -> list[bigquery.SchemaField]:
    return [*(bigquery.SchemaField(n, bigquery_type(n, k)) for n, k in table.columns), *metadata]


def bigquery_type(name: str, kind: str) -> str:
    if NUMERIC.fullmatch(kind):
        return "NUMERIC"
    if kind not in TYPES:
        raise WarehouseError(f"column {name!r} has no BigQuery type for {kind!r}", transient=False)
    return TYPES[kind]


def label(value: str) -> str:
    """A job label value by BigQuery's rules: at most 63 lowercase letters, digits, `_` and `-`."""
    return re.sub(r"[^a-z0-9_-]", "_", value.lower())[:63]


def warehouse_error(e: BaseException) -> WarehouseError:
    transient = isinstance(e, TRANSIENT) or bool(TRANSIENT_MESSAGE.search(str(e)))
    return WarehouseError(f"BigQuery: {e}", transient=transient)


def ndjson(table: Table, rows: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]) -> bytes:
    """The rows' data columns and the load's metadata as NDJSON, which the staging load reads."""
    names = [name for name, _ in table.columns]
    meta = {name: _json_value(value) for name, value in metadata.items()}
    return "".join(
        json.dumps({**{n: row[n] for n in names}, **meta}, default=str, separators=(",", ":"))
        + "\n"
        for row in rows
    ).encode("utf-8")


def _json_value(value: Any) -> Any:
    return value.isoformat(sep=" ") if isinstance(value, datetime) else value


class BigQueryWarehouse:
    def __init__(
        self,
        connect: Callable[[], bigquery.Client],
        *,
        dataset: str = DATASET,
        maximum_bytes_billed: int,
    ) -> None:
        self._connect = connect
        self._dataset = dataset
        self._maximum_bytes_billed = maximum_bytes_billed

    def _call(self, work: Callable[[bigquery.Client], Any]) -> Any:
        try:
            return work(self._connect())
        except WarehouseError:
            raise
        except ERRORS as e:
            raise warehouse_error(e) from e

    def _table_id(self, bq: bigquery.Client, name: str) -> str:
        return f"{bq.project}.{self._dataset}.{name}"

    # ---- tables --------------------------------------------------------------------------------

    def ensure_table(self, table: Table) -> None:
        self._ensure(table, PAGE_METADATA)

    def ensure_file_table(self, table: Table) -> None:
        self._ensure(table, FILE_METADATA)

    def _ensure(self, table: Table, metadata: Sequence[bigquery.SchemaField]) -> None:
        schema = schema_of(table, metadata)

        def ensure(bq: bigquery.Client) -> None:
            # Read first, then create: metadata calls are free, and the emulator answers an
            # existing table's create with a 500 that the client would retry until its deadline.
            table_id = self._table_id(bq, table.name)
            try:
                bq.get_table(table_id, retry=RETRY, timeout=TIMEOUT)
                return
            except api_exceptions.NotFound:
                pass
            with suppress(api_exceptions.Conflict):  # another worker created it first
                bq.create_table(bigquery.Table(table_id, schema), retry=RETRY, timeout=TIMEOUT)

        self._call(ensure)

    # ---- loads ---------------------------------------------------------------------------------

    def replace_page(self, table: Table, load: PageLoad, rows: Sequence[Mapping[str, Any]]) -> int:
        scope = PAGE_SCOPE if load.page == 0 else f"{PAGE_SCOPE} and _page = @page"
        params = [
            bigquery.ScalarQueryParameter("run_id", "STRING", load.run_id),
            bigquery.ScalarQueryParameter("interval_start", "TIMESTAMP", load.interval.start),
            bigquery.ScalarQueryParameter("interval_end", "TIMESTAMP", load.interval.end),
        ]
        if load.page:
            params.append(bigquery.ScalarQueryParameter("page", "INT64", load.page))
        metadata = {
            "_run_id": load.run_id,
            "_interval_start": load.interval.start,
            "_interval_end": load.interval.end,
            "_page": load.page,
            "_source_uri": load.source_uri,
        }

        def replace(bq: bigquery.Client) -> None:
            target = self._table_id(bq, table.name)
            staged = (table, PAGE_METADATA, rows, metadata, load.run_id)
            with self._staged(bq, *staged) as (staging, columns):
                sql = REPLACE.format(
                    table=target, scope=scope, columns=columns, staging=staging, guard=""
                )
                self._query(bq, sql, params, _labels("replace-page", table, load.run_id))

        self._call(replace)
        return len(rows)

    def replace_file(
        self, table: Table, load: FileLoad, rows: Sequence[Mapping[str, Any]]
    ) -> int | None:
        params = [
            bigquery.ScalarQueryParameter("source_uri", "STRING", load.source_uri),
            bigquery.ScalarQueryParameter("generation", "INT64", load.generation),
        ]
        metadata = {
            "_run_id": load.run_id,
            "_source_uri": load.source_uri,
            "_generation": load.generation,
        }

        def replace(bq: bigquery.Client) -> bool:
            target = self._table_id(bq, table.name)
            newer = NEWER.format(table=target)
            # Checked first, so a superseded generation costs no load; the transaction checks again
            # (a newer generation that commits in between: its rows stay, this one's never land).
            if self._query(bq, newer, params, _labels("check-file", table, load.run_id)):
                return False
            staged = (table, FILE_METADATA, rows, metadata, load.run_id)
            with self._staged(bq, *staged) as (staging, columns):
                sql = REPLACE.format(
                    table=target,
                    scope=FILE_SCOPE,
                    columns=columns,
                    staging=staging,
                    guard=f" and not exists ({newer})",
                )
                self._query(bq, sql, params, _labels("replace-file", table, load.run_id))
            return True

        return len(rows) if self._call(replace) else None

    @contextmanager
    def _staged(
        self,
        bq: bigquery.Client,
        table: Table,
        metadata_schema: Sequence[bigquery.SchemaField],
        rows: Sequence[Mapping[str, Any]],
        metadata: Mapping[str, Any],
        run_id: str,
    ) -> Iterator[tuple[str, str]]:
        """A staging table holding one load's rows and their metadata (all but `_loaded_at`):
        created with an expiry, filled by a load job (free), and dropped once the replace is done,
        whether it committed or not. Yields its id and its column list."""
        schema = schema_of(table, [f for f in metadata_schema if f.name in metadata])
        staging = bigquery.Table(
            self._table_id(bq, f"elf_staging_{table.name}_{uuid.uuid4().hex[:12]}"), schema
        )
        staging.expires = datetime.now(UTC) + STAGING_TTL
        bq.create_table(staging, retry=RETRY, timeout=TIMEOUT)
        try:
            if rows:
                config = bigquery.LoadJobConfig(
                    schema=schema,
                    source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                    labels=_labels("stage", table, run_id),
                )
                job = bq.load_table_from_file(
                    io.BytesIO(ndjson(table, rows, metadata)),
                    staging.reference,
                    job_config=config,
                    timeout=TIMEOUT,
                )
                job.result(timeout=TIMEOUT, retry=RETRY)
            columns = ", ".join(f"`{field.name}`" for field in schema)
            yield f"{staging.project}.{staging.dataset_id}.{staging.table_id}", columns
        finally:
            try:
                bq.delete_table(staging.reference, not_found_ok=True, retry=RETRY, timeout=TIMEOUT)
            except ERRORS as e:
                # The load stands; the table expires on its own.
                log.warning("could not drop the staging table %s: %s", staging.table_id, e)

    def _query(
        self,
        bq: bigquery.Client,
        sql: str,
        params: list[bigquery.ScalarQueryParameter],
        labels: dict[str, str],
    ) -> list[Any]:
        config = bigquery.QueryJobConfig(
            query_parameters=params,
            maximum_bytes_billed=self._maximum_bytes_billed,
            labels=labels,
        )
        job = bq.query(sql, job_config=config, timeout=TIMEOUT, retry=RETRY, job_retry=JOB_RETRY)
        return list(job.result(timeout=TIMEOUT, retry=RETRY, job_retry=JOB_RETRY))


def _labels(purpose: str, table: Table, run_id: str) -> dict[str, str]:
    return {
        "component": "el-factory",
        "purpose": purpose,
        "table": label(table.name),
        "run": label(run_id),
    }
