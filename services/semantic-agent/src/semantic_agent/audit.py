"""One audit row per data query an agent runs (semantic/PLAN.md SL-10).

Both agents set `audit_tool_call` as ADK's `after_tool_callback`, so the tools stay as they are and
every `query_metrics` and `execute_sql` call, answered or refused, lands in `ops.agent_queries`:
which agent, user, session and call; the metrics, filters and dates or the SQL; the rows returned;
the freshness statement; the error. The row is written as `agent_audit`, a role that may only
insert into that table, never as the agent's own read role: the baseline runs whatever SQL its
model writes, so a role that could write the audit could also forge it.

An audit that cannot be written withholds the result: the model gets an error instead of rows.

Env: `AUDIT_URL`, else dbt's own `DBT_*` host, port and database (as freshness.py) with the
`agent_audit` login, so the audit lands in the warehouse the query read.
"""

from __future__ import annotations

import os
from typing import Any

import psycopg
from google.adk.tools import BaseTool, ToolContext
from psycopg.types.json import Jsonb

AUDITED = ("query_metrics", "execute_sql")
"""The tools that read the warehouse; listing and describing metrics read only the catalog."""

SQL = """
insert into ops.agent_queries (
  agent, tool, user_id, session_id, invocation_id, call_id,
  metrics, filters, arguments, sql, rows_returned, freshness, error
) values (
  %(agent)s, %(tool)s, %(user_id)s, %(session_id)s, %(invocation_id)s, %(call_id)s,
  %(metrics)s, %(filters)s, %(arguments)s, %(sql)s, %(rows_returned)s, %(freshness)s, %(error)s
)
"""


def _url() -> str:
    if url := os.environ.get("AUDIT_URL"):
        return url
    env = os.environ.get
    host, port = env("DBT_HOST", "warehouse"), env("DBT_PORT", "5432")
    return f"postgresql://agent_audit:agent_audit@{host}:{port}/{env('DBT_DBNAME', 'warehouse')}"


def audit_row(
    tool: str, args: dict[str, Any], context: ToolContext, response: dict[str, Any]
) -> dict[str, Any]:
    """The audit row of one tool call: what was asked, by whom, and what came back."""
    rows = response.get("rows")
    freshness = response.get("freshness") or {}
    return {
        "agent": context.agent_name,
        "tool": tool,
        "user_id": context.user_id,
        "session_id": context.session.id,
        "invocation_id": context.invocation_id,
        "call_id": context.function_call_id,
        "metrics": args.get("metrics") or response.get("metrics"),
        "filters": args.get("filters"),
        "arguments": args,
        # The model's own SQL for the baseline, the SQL MetricFlow compiled for the semantic agent.
        "sql": args.get("sql") or response.get("sql"),
        "rows_returned": len(rows) if isinstance(rows, list) else None,
        "freshness": freshness.get("statement"),
        "error": response.get("error"),
    }


def record(row: dict[str, Any]) -> None:
    """Writes one audit row; raises psycopg.Error when it cannot."""
    params = {
        **row,
        "filters": Jsonb(row["filters"]) if row["filters"] is not None else None,
        "arguments": Jsonb(row["arguments"]),
    }
    with psycopg.connect(_url(), connect_timeout=10) as conn:
        conn.execute(SQL, params)


def audit_tool_call(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: Any
) -> dict[str, Any] | None:
    """ADK's after_tool_callback: audits a data query, and withholds its result if it can't."""
    if tool.name not in AUDITED:
        return None
    response = tool_response if isinstance(tool_response, dict) else {}
    try:
        record(audit_row(tool.name, args, tool_context, response))
    except psycopg.Error as e:
        reason = str(e).strip().splitlines()[0]
        return {
            "error": f"the query ran but its audit row could not be written ({reason}), so "
            f"its result is withheld; say that the answer is unavailable"
        }
    return None
