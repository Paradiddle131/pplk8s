"""The semantic agent: answers business questions through the semantic layer's metrics only.

`adk api_server src` and `adk web src` serve `root_agent` (semantic/PLAN.md SL-2).
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.tools import FunctionTool

from semantic_agent.model import build_model
from semantic_agent.tools import TOOLS

INSTRUCTION = """\
You answer business questions about the lab's sales, partner returns and finance data.
Every number you give must come from the query_metrics tool in this turn; never compute,
estimate or recall a figure yourself, and never write SQL.
Steps: call list_metrics; pick the metric whose description matches the question; call
describe_metric when you need its dimensions; call query_metrics.
Revenue, orders, cancellations, returns and net revenue each have exactly one definition, the
metric's; use it even when the question's wording suggests another.
If no metric answers the question, say that the semantic layer has no such metric and name the
closest metrics; do not answer from general knowledge.
Answer in one or two sentences: the figure with its unit, and the days or period it covers.
"""


def build_agent(model: BaseLlm | str | None = None) -> LlmAgent:
    return LlmAgent(
        name="semantic_agent",
        description="Answers business questions through the dbt semantic layer's metrics.",
        model=model or build_model(),
        instruction=INSTRUCTION,
        tools=[FunctionTool(tool) for tool in TOOLS],
    )


root_agent = build_agent()
