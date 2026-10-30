"""The eval baseline: the same model with one `execute_sql` tool over gold and exposed.

The "ADK schema-driven" pattern (semantic/PLAN.md SL-5): the agent is told which tables exist and
infers their columns and the SQL itself, with no semantic guardrails. The database enforces the
scope: the lab's `agent_sql` role may only read `gold`, `exposed` and their `information_schema`
rows, and every statement runs read-only under a timeout.

Env: `WAREHOUSE_SQL_URL` (default the Compose warehouse as `agent_sql`, database `DBT_DBNAME`).
"""

from __future__ import annotations

import datetime
import decimal
import os
from typing import Any

import psycopg
from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.tools import FunctionTool

from semantic_agent.model import answer_model_failure, build_model

MAX_ROWS = 200
TABLES = (
    "gold.daily_sales, gold.customer_lifetime, gold.daily_weather, gold.tlc_daily_trips, "
    "exposed.sales_by_country_daily, exposed.daily_sales_with_weather, exposed.net_sales_daily, "
    "exposed.tlc_daily_trips_by_borough"
)

INSTRUCTION = f"""\
You answer business questions about the lab's sales, partner returns and finance data by writing
PostgreSQL for the execute_sql tool. The tables you may read are: {TABLES}.
Find their columns with information_schema.columns when you need them.
Every number you give must come from a query result in this turn.
If the tables cannot answer the question, say so.
Answer in one or two sentences: the figure with its unit, and the days or period it covers.
"""


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
                cursor.execute(sql.strip().rstrip(";"))  # type: ignore[arg-type]
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
        instruction=INSTRUCTION,
        tools=[FunctionTool(execute_sql)],
        on_model_error_callback=answer_model_failure,
    )


root_agent = build_agent()
