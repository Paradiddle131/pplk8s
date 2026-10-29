"""What the database enforces, and where sessions live: needs `make services-up`."""

import asyncio
import uuid

import psycopg
import pytest
from google.adk.events import Event
from google.adk.sessions import DatabaseSessionService
from google.genai import types

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
