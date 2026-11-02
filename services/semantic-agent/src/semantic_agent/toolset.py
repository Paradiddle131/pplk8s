"""The toolset seam: the tools the semantic agent answers through (semantic/PLAN.md SL-2, #207).

`AGENT_TOOLSET` picks the implementation (seam.py): `metricflow` (the default: the lab's three
metric tools over MetricFlow, `toolset_metricflow.py`) or `data_agent` (a native BigQuery data
agent built from the same generated context, through ADK's `DataAgentToolset`,
`toolset_data_agent.py`). A toolset names the tools that read only the catalog; every other tool's
calls are audited and given their freshness by the agent's after-tool callback (guard.py), so both
survive the swap.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from google.adk.tools import BaseTool
from google.adk.tools.base_toolset import BaseToolset

from semantic_agent.seam import choose

# The implementation of each AGENT_TOOLSET value, imported only when chosen.
IMPLEMENTATIONS = {
    "metricflow": "semantic_agent.toolset_metricflow",
    "data_agent": "semantic_agent.toolset_data_agent",
}


@dataclass(frozen=True)
class Toolset:
    """What the agent is built over: its tools, the ones among them that read only the catalog
    (never audited), and the instruction that tells the model how to use them."""

    tools: Sequence[BaseTool | BaseToolset]
    catalog_tools: tuple[str, ...]
    instruction: str


def toolset() -> Toolset:
    """The toolset AGENT_TOOLSET names (default `metricflow`), its module imported when chosen."""
    return choose("AGENT_TOOLSET", IMPLEMENTATIONS, default="metricflow").toolset()
