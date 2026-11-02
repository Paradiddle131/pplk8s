"""One audit row per data query an agent runs (semantic/PLAN.md SL-10).

Both agents' `after_tool_callback` and the MCP server (guard.py) call `audit` for every call to a
data tool, every tool but the catalog ones, so the tools stay as they are and each call, answered or
refused, lands in `ops.agent_queries`: which agent, user, session and call (a `Caller`); the
metrics, filters and dates or the SQL; the rows returned; the freshness statement; the error. The
row is written as `agent_audit`, a role that may only insert into that table, never as the agent's
own read role: the baseline runs whatever SQL its model writes, so a role that could write the
audit could also forge it.

An audit that cannot be written withholds the result: the model gets an error instead of rows.

The row goes through the warehouse seam (warehouse.py): on Postgres as `agent_audit` (`AUDIT_URL`,
else dbt's own `DBT_*` host, port and database with that login, so the audit lands in the warehouse
the query read), on BigQuery by a DML insert as the `agent-audit` service account
(`AUDIT_SERVICE_ACCOUNT`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from google.adk.tools import ToolContext

from semantic_agent.warehouse import WarehouseError, reason, warehouse


@dataclass(frozen=True)
class Caller:
    """Who made a tool call: the agent (an ADK agent's name, or an MCP client's), the end user when
    the caller knows one, its session, the turn (an ADK invocation) and the call itself."""

    agent: str
    user_id: str | None = None
    session_id: str | None = None
    invocation_id: str | None = None
    call_id: str | None = None

    @classmethod
    def of(cls, context: ToolContext) -> Caller:
        """The caller of an ADK tool call."""
        return cls(
            agent=context.agent_name,
            user_id=context.user_id,
            session_id=context.session.id,
            invocation_id=context.invocation_id,
            call_id=context.function_call_id,
        )


def audit_row(
    tool: str, args: dict[str, Any], caller: Caller, response: dict[str, Any]
) -> dict[str, Any]:
    """The audit row of one tool call: what was asked, by whom, and what came back."""
    rows = response.get("rows")
    freshness = response.get("freshness") or {}
    return {
        "agent": caller.agent,
        "tool": tool,
        "user_id": caller.user_id,
        "session_id": caller.session_id,
        "invocation_id": caller.invocation_id,
        "call_id": caller.call_id,
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
    """Writes one audit row; raises WarehouseError when it cannot."""
    warehouse().insert_audit(row)


def audit(
    tool: str, args: dict[str, Any], caller: Caller, response: dict[str, Any]
) -> dict[str, Any] | None:
    """Audits one data call; returns the error that withholds its result when it cannot."""
    try:
        record(audit_row(tool, args, caller, response))
    except WarehouseError as e:
        return {
            "error": f"the query ran but its audit row could not be written ({reason(e)}), so "
            f"its result is withheld; say that the answer is unavailable"
        }
    return None
