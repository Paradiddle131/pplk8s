"""What every data call gets, whichever toolset fills the seam (semantic/PLAN.md SL-4, SL-10; #177).

The toolset is the part that changes at work (`DataAgentToolset` for the lab's MetricFlow tools), so
the freshness and the audit are not the toolset's: `guarded` gives every call to a data tool,
answered or refused, its audit row and attaches its metrics' freshness to an answered one. Two
surfaces call it: `after_data_tool`, ADK's `after_tool_callback`, and the MCP server
(mcp_server.py), so an agent outside ADK gets the same audit and freshness. A data tool is every
tool but the ones the seam names as reading only the catalog, so a tool the seam forgets to name is
audited, not skipped.

ADK stops at the first after-tool callback that returns a value, so the two steps are one function:
freshness first, so the audit row holds the statement the model is shown.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

from google.adk.tools import BaseTool, ToolContext

from semantic_agent import audit
from semantic_agent import freshness as ledger
from semantic_agent.metrics import Catalog, QueryError

AfterTool = Callable[[BaseTool, dict[str, Any], ToolContext, Any], dict[str, Any] | None]


def metrics_named(args: dict[str, Any], response: dict[str, Any]) -> list[str]:
    """The metrics a data call answered with: the ones its result names, else the ones it asked."""
    named = response.get("metrics") or args.get("metrics") or []
    return [name for name in named if isinstance(name, str)]


def products(metrics: list[str], catalog: Catalog) -> list[str]:
    """The readiness products the metrics read, from the catalog; an unknown metric names none."""
    found = set()
    for name in metrics:
        try:
            found.update(catalog.metric(name).get("readiness", []))
        except QueryError:
            continue
    return sorted(found)


def tables_named(response: dict[str, Any]) -> list[str]:
    """The tables a data call's generated SQL reads (a data agent's answer names no metrics)."""
    return audit.tables_read(audit.generated_sql(response))


def freshness_of(
    tool: str,
    metrics: list[str],
    catalog: Catalog,
    caller: audit.Caller | None = None,
    tables: list[str] | None = None,
) -> dict[str, Any]:
    """The freshness of the metrics a call answered with, else of the semantic models' and the
    governed tables its SQL read (a governed table's are its metrics', SL-24), or why there is
    none; the ledger read names the `caller` where the warehouse records who asked (BigQuery's job
    labels)."""
    found = products(metrics, catalog) if metrics else catalog.readiness_of_tables(tables or [])
    if not metrics and not found:
        return {
            "products": [],
            "late": None,
            "statement": f"Freshness unknown: the {tool} result names no metrics and reads no "
            "semantic model's or governed table, so their readiness cannot be looked up.",
        }
    return ledger.freshness(
        found,
        agent=caller.agent if caller else None,
        session_id=caller.session_id if caller else None,
    )


def guarded(
    tool: str,
    args: dict[str, Any],
    response: Any,
    caller: audit.Caller,
    catalog: Callable[[], Catalog] | None = None,
) -> dict[str, Any]:
    """What a data call's caller is shown: its result with, given the metric `catalog`, the
    freshness of the metrics an answered call named, once its audit row is written; or the error
    that withholds the result when the row cannot be written."""
    response = response if isinstance(response, dict) else {"result": response}
    if catalog is not None and not audit.error_of(response) and "freshness" not in response:
        metrics = metrics_named(args, response)
        tables = [] if metrics else tables_named(response)
        freshness = freshness_of(tool, metrics, catalog(), caller, tables)
        response = {**response, "freshness": freshness}
    withheld = audit.audit(tool, args, caller, response)
    return withheld if withheld is not None else response


def after_data_tool(
    catalog_tools: Collection[str], catalog: Callable[[], Catalog] | None = None
) -> AfterTool:
    """ADK's after_tool_callback for an agent: audits every call to a tool not in `catalog_tools`
    and, given the metric `catalog`, attaches the freshness of an answered call's metrics."""

    def callback(
        tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: Any
    ) -> dict[str, Any] | None:
        if tool.name in catalog_tools:
            return None
        caller = audit.Caller.of(tool_context)
        response = guarded(tool.name, args, tool_response, caller, catalog)
        return response if response is not tool_response else None

    return callback
