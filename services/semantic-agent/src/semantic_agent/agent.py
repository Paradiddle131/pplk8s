"""The semantic agent: answers business questions through the semantic layer's metrics only.

`adk api_server src` and `adk web src` serve `root_agent` (semantic/PLAN.md SL-2), over the
toolset `AGENT_TOOLSET` names (toolset.py): the lab's MetricFlow tools, or a native data agent.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm

from semantic_agent.guard import after_data_tool
from semantic_agent.model import answer_model_failure, build_model, request_config
from semantic_agent.tools import catalog
from semantic_agent.toolset import Toolset
from semantic_agent.toolset import toolset as chosen_toolset


def build_agent(model: BaseLlm | str | None = None, toolset: Toolset | None = None) -> LlmAgent:
    """The agent over a toolset, the one AGENT_TOOLSET names (toolset.py) unless given one: every
    call to a tool the toolset does not name as reading only the catalog is audited and given its
    freshness, whatever the tool is called."""
    toolset = toolset or chosen_toolset()
    return LlmAgent(
        name="semantic_agent",
        description="Answers business questions through the dbt semantic layer's metrics.",
        model=model or build_model(),
        generate_content_config=request_config(),
        instruction=toolset.instruction,
        tools=list(toolset.tools),
        after_tool_callback=after_data_tool(toolset.catalog_tools, catalog),
        on_model_error_callback=answer_model_failure,
    )


def __getattr__(name: str) -> LlmAgent:
    """`root_agent`, built on first use (PEP 562) and kept: `adk api_server` reads it as before,
    while importing the package (`python -m semantic_agent.bet_eval` does) builds no model, so a
    Claude pass without its key is skipped with that reason rather than a traceback (#365)."""
    if name == "root_agent":
        built = build_agent()
        globals()["root_agent"] = built
        return built
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
