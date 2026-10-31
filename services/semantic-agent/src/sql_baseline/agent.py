"""The eval baseline: the same model with one `execute_sql` tool over gold and exposed.

The "ADK schema-driven" pattern (semantic/PLAN.md SL-5): the agent is told which tables exist and
infers their columns and the SQL itself, with no semantic guardrails. The tables are the catalog's
public models, the ones the semantic agent's catalog is built from, so neither agent knows a table
the other does not. The database enforces the scope: the lab's `agent_sql` role may only read
`gold`, `exposed` and their `information_schema` rows, and every call runs one statement, read-only
under a timeout. It is the eval's control only: `make agent-eval` runs it in-process, and it is
never deployed.

Env: `WAREHOUSE_SQL_URL` (default the Compose warehouse as `agent_sql`, database `DBT_DBNAME`).
"""

from __future__ import annotations

import datetime
import decimal
import os
from typing import Any

import psycopg
from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.base_llm import BaseLlm
from google.adk.tools import FunctionTool

from semantic_agent.audit import audit_tool_call
from semantic_agent.metrics import Catalog
from semantic_agent.model import answer_model_failure, build_model, request_config
from semantic_agent.tools import catalog

MAX_ROWS = 200

INSTRUCTION = """\
You answer business questions about the data in the warehouse's tables by writing PostgreSQL for
the execute_sql tool. The tables you may read are: {tables}.
Find their columns with information_schema.columns when you need them.
Every number you give must come from a query result in this turn.
If the tables cannot answer the question, say so.
Answer in one or two sentences: the figure with its unit, and the days or period it covers.
"""


def tables(source: Catalog) -> list[str]:
    """The catalog's public models as `schema.table`, the names the warehouse knows them by."""
    return sorted(".".join(model["relation"].split(".")[-2:]) for model in source.models)


def instruction(_context: ReadonlyContext | None = None) -> str:
    """The instruction with the catalog's tables, read when the agent first runs, not on import."""
    return INSTRUCTION.format(tables=", ".join(tables(catalog())))


def _url() -> str:
    database = os.environ.get("DBT_DBNAME", "warehouse")
    default = f"postgresql://agent_sql:agent_sql@localhost:5433/{database}"
    return os.environ.get("WAREHOUSE_SQL_URL", default)


def _cell(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, datetime.date | datetime.datetime):
        return value.isoformat()
    return value


def execute_sql(sql: str) -> dict[str, Any]:
    """Runs one read-only PostgreSQL query on the warehouse and returns its rows.

    Args:
        sql: A single SELECT statement over the gold and exposed tables.
    """
    try:
        with psycopg.connect(_url(), connect_timeout=10, autocommit=False) as conn:
            conn.read_only = True
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '10s'")
                # The extended protocol (prepare) refuses a second statement, which could
                # otherwise end the read-only transaction or lift the timeout.
                cursor.execute(sql.strip().rstrip(";"), prepare=True)  # type: ignore[arg-type]
                if cursor.description is None:
                    return {"error": "the statement returned no rows; send a SELECT"}
                columns = [c.name for c in cursor.description]
                rows = cursor.fetchmany(MAX_ROWS + 1)
    except psycopg.Error as e:
        return {"error": str(e).strip().splitlines()[0]}
    return {
        "columns": columns,
        "rows": [dict(zip(columns, map(_cell, row), strict=True)) for row in rows[:MAX_ROWS]],
        "truncated": len(rows) > MAX_ROWS,
    }


def build_agent(model: BaseLlm | str | None = None) -> LlmAgent:
    return LlmAgent(
        name="sql_baseline",
        description="Answers business questions with SQL over gold and exposed (eval baseline).",
        model=model or build_model(),
        generate_content_config=request_config(),
        instruction=instruction,
        tools=[FunctionTool(execute_sql)],
        after_tool_callback=audit_tool_call,
        on_model_error_callback=answer_model_failure,
    )


root_agent = build_agent()
