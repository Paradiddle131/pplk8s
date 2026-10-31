"""What the database enforces, and where sessions live: needs `make services-up`."""

import asyncio
import uuid

import psycopg
import pytest
from google.adk.events import Event
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from semantic_agent.audit import record  # the real writer: conftest's `audit` stubs the module's
from sql_baseline.agent import _url, execute_sql
from tests.conftest import service_unreachable

SESSIONS_URL = "postgresql+asyncpg://agent_sessions:agent_sessions@localhost:5434/agent_sessions"


@pytest.fixture
def warehouse(monkeypatch):
    monkeypatch.setenv("DBT_DBNAME", "warehouse")
    try:
        psycopg.connect(_url(), connect_timeout=3).close()
    except psycopg.Error as e:
        service_unreachable("the warehouse as agent_sql", e)


def test_the_baseline_reads_its_schemas(warehouse):
    assert execute_sql("select count(*) as n from information_schema.schemata")["rows"]


@pytest.mark.parametrize(
    ("sql", "refusal"),
    [
        ("select * from ops.readiness", "permission denied for schema ops"),
        ("select * from silver.orders", "silver"),
        ("create table gold.planted (a int)", "read-only transaction"),
        ("select pg_sleep(11)", "statement timeout"),
    ],
)
def test_the_baseline_is_read_only_and_scoped_by_its_role(warehouse, sql, refusal):
    assert refusal in execute_sql(sql)["error"]


def test_sessions_survive_a_new_session_service_on_postgres():
    async def go():
        user = f"u-{uuid.uuid4().hex[:8]}"
        first = DatabaseSessionService(db_url=SESSIONS_URL)
        session = await first.create_session(app_name="semantic_agent", user_id=user)
        content = types.Content(role="user", parts=[types.Part(text="revenue yesterday?")])
        await first.append_event(session, Event(author="user", content=content))
        again = await DatabaseSessionService(db_url=SESSIONS_URL).get_session(
            app_name="semantic_agent", user_id=user, session_id=session.id
        )
        return again

    try:
        again = asyncio.run(go())
    except (OSError, ConnectionError) as e:
        service_unreachable("the agent_sessions database on the metadata DB", e)
    assert again is not None
    assert again.events[0].content.parts[0].text == "revenue yesterday?"


WAREHOUSE = "postgresql://{role}:{role}@localhost:5433/warehouse"


@pytest.fixture
def audit_db(monkeypatch):
    """The real audit writer against the warehouse's ops.agent_queries, as agent_audit."""
    monkeypatch.setenv("AUDIT_URL", WAREHOUSE.format(role="agent_audit"))
    try:
        psycopg.connect(WAREHOUSE.format(role="agent_audit"), connect_timeout=3).close()
    except psycopg.Error as e:
        service_unreachable("the warehouse as agent_audit", e)


def test_an_audit_row_lands_in_ops_agent_queries(audit_db):
    session = f"s-{uuid.uuid4().hex[:8]}"
    record(
        {
            "agent": "semantic_agent",
            "tool": "query_metrics",
            "user_id": "u",
            "session_id": session,
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
    )
    with psycopg.connect(WAREHOUSE.format(role="warehouse")) as conn:
        row = conn.execute(
            "select agent, metrics, filters->0->>'dimension', rows_returned, called_at is not null"
            " from ops.agent_queries where session_id = %s",
            [session],
        ).fetchone()
    assert row == ("semantic_agent", ["orders_total"], "order__status", 1, True)


@pytest.mark.parametrize(
    ("sql", "refusal"),
    [
        ("select * from ops.agent_queries", "permission denied for table agent_queries"),
        ("update ops.agent_queries set error = 'x'", "permission denied for table agent_queries"),
        ("delete from ops.agent_queries", "permission denied for table agent_queries"),
        ("insert into ops.readiness (product) values ('x')", "permission denied for table"),
        ("create table ops.planted (a int)", "permission denied for schema ops"),
    ],
)
def test_the_audit_writer_may_only_insert_into_the_audit(audit_db, sql, refusal):
    with (
        pytest.raises(psycopg.Error, match=refusal),
        psycopg.connect(WAREHOUSE.format(role="agent_audit")) as conn,
    ):
        conn.execute(sql)


@pytest.mark.parametrize("role", ["agent_sql", "agent_metrics"])
def test_no_agent_role_can_write_the_audit_even_in_a_read_write_transaction(audit_db, role):
    """A model's SQL can leave the read-only transaction (`commit; begin read write`), so the
    audit stays the agents' to write only through the audit writer's own role."""
    with (
        pytest.raises(psycopg.Error, match="permission denied"),
        psycopg.connect(WAREHOUSE.format(role=role), autocommit=True) as conn,
    ):
        conn.execute("begin read write")
        conn.execute(
            "insert into ops.agent_queries (agent, tool, arguments) values ('x', 'x', '{}')"
        )
