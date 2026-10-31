"""What every data call gets, whichever toolset fills the seam (semantic/PLAN.md SL-4, SL-10; #177).

The toolset is the part that changes at work (`DataAgentToolset` for the lab's MetricFlow tools), so
the freshness and the audit are not the toolset's: `after_data_tool` builds ADK's
`after_tool_callback` that gives every call to a data tool, answered or refused, its audit row and
attaches its metrics' freshness to an answered one. A data tool is every tool but the ones the seam
names as reading only the catalog, so a tool the seam forgets to name is audited, not skipped.

ADK stops at the first after-tool callback that returns a value, so the two steps are one callback:
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


def freshness_of(tool: str, metrics: list[str], catalog: Catalog) -> dict[str, Any]:
    """The freshness of the metrics a call answered with, or why there is none."""
    if not metrics:
        return {
            "products": [],
            "late": None,
            "statement": f"Freshness unknown: the {tool} result names no metrics, so their "
            "readiness cannot be looked up.",
        }
    return ledger.freshness(products(metrics, catalog))


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
        response = tool_response if isinstance(tool_response, dict) else {"result": tool_response}
        if catalog is not None and "error" not in response and "freshness" not in response:
            metrics = metrics_named(args, response)
            response = {**response, "freshness": freshness_of(tool.name, metrics, catalog())}
        withheld = audit.audit(tool.name, args, tool_context, response)
        if withheld is not None:
            return withheld
        return response if response is not tool_response else None

    return callback
