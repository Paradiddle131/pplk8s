"""The warehouse seam (semantic_agent/warehouse.py, #209): the factory, both implementations'
statements and parameters against stand-in clients, and every driver error as a WarehouseError."""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import create_autospec

import psycopg
import pytest
import yaml
from google.api_core.exceptions import Forbidden
from google.auth import impersonated_credentials
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

from semantic_agent import warehouse_bigquery, warehouse_postgres
from semantic_agent.audit import Caller, record
from semantic_agent.freshness import freshness
from semantic_agent.guard import guarded
from semantic_agent.warehouse import WarehouseError, warehouse

CAPS = Path(__file__).resolve().parents[3] / "platform" / "gcp" / "free-path.yaml"
ROW = {
    "agent": "semantic_agent",
    "tool": "query_metrics",
    "user_id": "u",
    "session_id": "S-1",
    "invocation_id": "e-1",
    "call_id": "c-1",
    "metrics": ["orders_total"],
    "filters": [{"dimension": "order__status", "operator": "=", "values": ["cancelled"]}],
    "arguments": {"metrics": ["orders_total"]},
    "sql": "SELECT 1",
    "rows_returned": 1,
    "freshness": "Fresh: sales.silver is ready up to 2026-10-03T00:00Z.",
    "error": None,
}
AUDIT_ACCOUNT = "agent-audit@lab-project.iam.gserviceaccount.com"
READY = datetime.datetime(2026, 10, 3, tzinfo=datetime.UTC)


# The factory.


def test_postgres_is_the_default(monkeypatch):
    monkeypatch.delenv("AGENT_WAREHOUSE", raising=False)
    assert isinstance(warehouse(), warehouse_postgres.PostgresWarehouse)


def test_bigquery_is_chosen_by_agent_warehouse(monkeypatch):
    monkeypatch.setenv("AGENT_WAREHOUSE", "bigquery")
    assert isinstance(warehouse(), warehouse_bigquery.BigQueryWarehouse)


def test_an_unknown_warehouse_is_a_warehouse_error(monkeypatch):
    monkeypatch.setenv("AGENT_WAREHOUSE", "snowflake")
    with pytest.raises(WarehouseError, match="AGENT_WAREHOUSE='snowflake' is not one of"):
        warehouse()


def test_a_missing_driver_names_the_extra_to_install(monkeypatch):
    monkeypatch.setenv("AGENT_WAREHOUSE", "bigquery")
    monkeypatch.setitem(sys.modules, "semantic_agent.warehouse_bigquery", None)
    with pytest.raises(WarehouseError, match="needs the 'bigquery' extra"):
        warehouse()


@pytest.mark.parametrize(
    ("choice", "imported", "absent"),
    [
        ("bigquery", {"google.cloud.bigquery"}, {"psycopg", "asyncpg"}),
        ("postgres", {"psycopg"}, {"google.cloud.bigquery"}),
    ],
)
def test_only_the_chosen_warehouses_driver_is_imported(choice, imported, absent):
    """The served agent imported as `adk api_server` does, then the chosen warehouse built: the
    other warehouse's driver stays out of the process (SL-19)."""
    code = (
        "import sys, semantic_agent\n"
        "from semantic_agent.warehouse import warehouse\n"
        "warehouse()\n"
        "print(sorted(m for m in sys.modules if m in "
        f"{sorted(imported | absent)!r}))\n"
    )
    env = {**os.environ, "AGENT_WAREHOUSE": choice}
    out = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    assert set(eval(out.stdout)) == imported  # noqa: S307 (the child's own repr of a list)


# Postgres: today's statements, moved.


class Connection:
    """psycopg.connect's stand-in: keeps each statement and its parameters."""

    def __init__(self, url: str, rows: list[tuple] | None = None, **kwargs: Any):
        self.url, self.kwargs, self.rows, self.executed = url, kwargs, rows or [], []

    def __enter__(self) -> Connection:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: dict[str, Any]) -> Connection:
        self.executed.append((sql, params))
        return self

    def fetchall(self) -> list[tuple]:
        return self.rows


@pytest.fixture
def postgres(monkeypatch):
    monkeypatch.delenv("AGENT_WAREHOUSE", raising=False)
    monkeypatch.delenv("AUDIT_URL", raising=False)
    for name, value in {"DBT_HOST": "db", "DBT_PORT": "6543", "DBT_DBNAME": "dw"}.items():
        monkeypatch.setenv(name, value)
    connections: list[Connection] = []

    def connect(url: str, **kwargs: Any) -> Connection:
        connections.append(Connection(url, [("sales.silver", READY, None)], **kwargs))
        return connections[-1]

    monkeypatch.setattr(warehouse_postgres.psycopg, "connect", connect)
    return connections


def test_postgres_inserts_the_audit_row_as_agent_audit(postgres):
    record(ROW)
    (conn,) = postgres
    assert conn.url == "postgresql://agent_audit:agent_audit@db:6543/dw"
    ((sql, params),) = conn.executed
    assert sql == warehouse_postgres.AUDIT_SQL
    assert params["filters"].obj == ROW["filters"] and params["arguments"].obj == ROW["arguments"]
    assert params["metrics"] == ["orders_total"]


def test_postgres_reads_the_ledger_with_dbts_login(postgres, monkeypatch):
    monkeypatch.setenv("DBT_USER", "agent_metrics")
    monkeypatch.setenv("DBT_PASSWORD", "secret")
    rows = warehouse().readiness(["sales.silver"], agent="semantic_agent", session_id="s")
    (conn,) = postgres
    assert conn.url == "postgresql://agent_metrics:secret@db:6543/dw"
    assert conn.executed == [(warehouse_postgres.READINESS_SQL, {"products": ["sales.silver"]})]
    assert rows == [("sales.silver", READY, None)]


def test_a_postgres_error_is_a_warehouse_error_with_its_first_line(monkeypatch):
    def refuse(url: str, **kwargs: Any) -> None:
        raise psycopg.OperationalError("connection refused\n\tIs the server running?")

    monkeypatch.setattr(warehouse_postgres.psycopg, "connect", refuse)
    with pytest.raises(WarehouseError, match=r"^connection refused$"):
        warehouse_postgres.PostgresWarehouse().insert_audit(ROW)
    with pytest.raises(WarehouseError, match=r"^connection refused$"):
        warehouse_postgres.PostgresWarehouse().readiness(["sales.silver"])


# BigQuery: DML and queries, capped and labelled, against a stand-in client.


class Job:
    def __init__(self, rows: list[tuple]):
        self.rows = rows

    def result(self, **kwargs: Any) -> list[tuple]:
        return self.rows


class Client:
    """bigquery.Client's stand-in: keeps every query job; has no streaming insert to call."""

    project = "lab-project"

    def __init__(self, rows: list[tuple] | None = None, error: Exception | None = None):
        self.rows, self.error, self.jobs = rows or [], error, []

    def query(self, sql: str, job_config: bigquery.QueryJobConfig, **kwargs: Any) -> Job:
        self.jobs.append((sql, job_config, kwargs))
        if self.error:
            raise self.error
        return Job(self.rows)


@pytest.fixture
def bq(monkeypatch):
    monkeypatch.setenv("AGENT_WAREHOUSE", "bigquery")
    monkeypatch.delenv("BQ_MAXIMUM_BYTES_BILLED", raising=False)
    monkeypatch.delenv("AUDIT_SERVICE_ACCOUNT", raising=False)
    fake = Client(rows=[("returns.silver", None, None), ("sales.silver", READY, 129600)])
    used: list[str] = []

    def client(impersonate: str = "") -> Client:
        used.append(impersonate)
        return fake

    monkeypatch.setattr(warehouse_bigquery, "_client", client)
    fake.impersonated = used
    return fake


def params(config: bigquery.QueryJobConfig) -> dict[str, Any]:
    return {
        p.name: (p.array_type, p.values)
        if isinstance(p, bigquery.ArrayQueryParameter)
        else (p.type_, p.value)
        for p in config.query_parameters
    }


def test_bigquery_inserts_the_audit_row_by_a_capped_labelled_dml_job(bq, monkeypatch):
    monkeypatch.setenv("AUDIT_SERVICE_ACCOUNT", AUDIT_ACCOUNT)
    record(ROW)
    ((sql, config, kwargs),) = bq.jobs
    assert bq.impersonated == [AUDIT_ACCOUNT]
    assert sql.strip().startswith("insert into `lab-project.ops.agent_queries`")
    assert "current_timestamp()" in sql and "parse_json(@arguments)" in sql
    cap = yaml.safe_load(CAPS.read_text())["caps"]["bigquery_maximum_bytes_billed"]
    assert config.maximum_bytes_billed == cap
    assert config.labels == {
        "component": "semantic-agent",
        "purpose": "audit",
        "agent": "semantic_agent",
        "session": "s-1",
    }
    assert kwargs["timeout"] and kwargs["retry"] is warehouse_bigquery.RETRY
    got = params(config)
    assert got["metrics"] == ("STRING", ["orders_total"])
    assert json.loads(got["filters"][1]) == ROW["filters"]
    assert json.loads(got["arguments"][1]) == ROW["arguments"]
    assert got["rows_returned"] == ("INT64", 1)
    assert got["error"] == ("STRING", None)
    assert set(got) == set(ROW) - {"called_at"}


def test_an_audit_row_without_metrics_or_filters_inserts_an_empty_array_and_null(bq):
    record({**ROW, "metrics": None, "filters": None, "rows_returned": None})
    got = params(bq.jobs[0][1])
    assert got["metrics"] == ("STRING", [])
    assert got["filters"] == ("STRING", None)
    assert got["rows_returned"] == ("INT64", None)


def test_bigquery_inserts_by_a_query_job_never_by_streaming(monkeypatch):
    """`insertAll` (insert_rows) has no free tier; a DML query job is free within the tier."""
    monkeypatch.setenv("AGENT_WAREHOUSE", "bigquery")
    client = create_autospec(bigquery.Client, instance=True)
    client.project = "lab-project"
    client.query.return_value.result.return_value = []
    monkeypatch.setattr(warehouse_bigquery, "_client", lambda impersonate="": client)
    record(ROW)
    client.query.assert_called_once()
    for streaming in ("insert_rows", "insert_rows_json", "insert_rows_from_dataframe"):
        getattr(client, streaming).assert_not_called()


def test_the_byte_cap_follows_its_env(bq, monkeypatch):
    monkeypatch.setenv("BQ_MAXIMUM_BYTES_BILLED", "1048576")
    record(ROW)
    assert bq.jobs[0][1].maximum_bytes_billed == 1048576


def test_bigquery_reads_the_ledger_as_the_postgres_one_returns_it(bq):
    rows = warehouse().readiness(
        ["returns.silver", "sales.silver"], agent="Claude Code", session_id="mcp.Session/42"
    )
    assert rows == [
        ("returns.silver", None, None),
        ("sales.silver", READY, datetime.timedelta(hours=36)),
    ]
    ((sql, config, _),) = bq.jobs
    assert bq.impersonated == [""]  # the agent's own identity reads the ledger
    assert "from unnest(@products)" in sql and "`lab-project.ops.product_deadlines`" in sql
    assert params(config) == {"products": ("STRING", ["returns.silver", "sales.silver"])}
    assert config.maximum_bytes_billed == warehouse_bigquery.DEFAULT_MAXIMUM_BYTES_BILLED
    assert config.labels == {
        "component": "semantic-agent",
        "purpose": "freshness",
        "agent": "claude_code",
        "session": "mcp_session_42",
    }


def test_a_data_call_labels_its_freshness_read_and_its_audit_with_its_session(bq, monkeypatch):
    """Through guard.guarded, as ADK's callback and the MCP server call it: both jobs name the
    caller, and the BigQuery ledger's answer becomes the statement the audit records."""
    from semantic_agent import audit, tools
    from semantic_agent import freshness as ledger

    monkeypatch.setattr(audit, "record", record)
    monkeypatch.setattr(ledger, "freshness", freshness)
    caller = Caller(agent="semantic_agent", session_id="sess-9")
    result = guarded(
        "query_metrics", {"metrics": ["revenue_eur"]}, {"rows": []}, caller, tools.catalog
    )
    assert "Late: sales.silver is ready only up to" in result["freshness"]["statement"]
    assert [c.labels["purpose"] for _, c, _ in bq.jobs] == ["freshness", "audit"]
    assert {c.labels["session"] for _, c, _ in bq.jobs} == {"sess-9"}
    assert params(bq.jobs[1][1])["freshness"][1] == result["freshness"]["statement"]


def test_a_bigquery_error_is_a_warehouse_error(bq):
    bq.error = Forbidden("Access Denied: Table lab-project:ops.agent_queries\nmore")
    with pytest.raises(WarehouseError, match=r"^403 Access Denied: Table lab-project:ops"):
        record(ROW)
    assert freshness(["sales.silver"])["statement"] == (
        "Freshness unknown: the readiness ledger could not be read "
        "(403 Access Denied: Table lab-project:ops.agent_queries)."
    )


# BigQuery's client: the project, the emulator and the audit's identity.


@pytest.fixture
def client_env(monkeypatch):
    warehouse_bigquery.client.cache_clear()
    for name in ("BQ_API_ENDPOINT", "GCP_ACCESS_TOKEN", "AUDIT_SERVICE_ACCOUNT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GCP_PROJECT", "lab-project")
    yield monkeypatch
    warehouse_bigquery.client.cache_clear()


def test_the_project_is_required(client_env):
    client_env.delenv("GCP_PROJECT")
    with pytest.raises(WarehouseError, match="GCP_PROJECT is unset"):
        warehouse_bigquery.BigQueryWarehouse().insert_audit(ROW)


def test_the_emulator_takes_no_credentials_and_no_impersonation(client_env):
    client_env.setenv("BQ_API_ENDPOINT", "http://localhost:9050")
    bq = warehouse_bigquery._client()
    assert bq.project == "lab-project"
    assert isinstance(bq._credentials, AnonymousCredentials)
    with pytest.raises(WarehouseError, match="AUDIT_SERVICE_ACCOUNT needs real BigQuery"):
        warehouse_bigquery._client(AUDIT_ACCOUNT)


def test_the_audit_impersonates_its_service_account(client_env):
    import google.auth

    source = AnonymousCredentials()
    client_env.setattr(google.auth, "default", lambda scopes: (source, "lab-project"))
    reader = warehouse_bigquery._client()
    writer = warehouse_bigquery._client(AUDIT_ACCOUNT)
    assert reader._credentials is source and reader.location == "US"
    assert isinstance(writer._credentials, impersonated_credentials.Credentials)
    assert writer._credentials._target_principal == AUDIT_ACCOUNT
    # the agent's own credentials, copied with the scopes impersonation needs
    assert isinstance(writer._credentials._source_credentials, AnonymousCredentials)


@pytest.mark.parametrize(
    ("value", "label"),
    [
        ("semantic_agent", "semantic_agent"),
        ("Claude Code", "claude_code"),
        ("3f2a-B9.x@y", "3f2a-b9_x_y"),
        ("x" * 70, "x" * 63),
    ],
)
def test_labels_follow_bigquerys_rules(value, label):
    assert warehouse_bigquery.label(value) == label
