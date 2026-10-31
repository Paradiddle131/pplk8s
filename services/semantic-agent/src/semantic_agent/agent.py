"""The semantic agent: answers business questions through the semantic layer's metrics only.

`adk api_server src` and `adk web src` serve `root_agent` (semantic/PLAN.md SL-2).
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.tools import FunctionTool

from semantic_agent.model import answer_model_failure, build_model, request_config
from semantic_agent.tools import TOOLS

INSTRUCTION = """\
You answer business questions about the lab's sales, partner returns and finance data.
Every number you give must come from the query_metrics tool in this turn; never compute,
estimate or recall a figure yourself, and never write SQL.
Steps: call list_metrics; pick the metric whose description matches the question; call
describe_metric when you need its dimensions; call query_metrics.
Revenue, orders, cancellations, returns and net revenue each have exactly one definition, the
metric's; use it even when the question's wording suggests another.
A question about a subset (orders with a given status, returns with a given reason) is a metric
with a filter on one of the dimensions describe_metric lists, not a missing metric.
A term the question uses may be in the glossary list_metrics returns: use the metrics and
dimensions the term names.
If no metric answers the question, say that the semantic layer has no such metric and name the
closest metrics; do not answer from general knowledge.
Answer in one or two sentences: the figure with its unit, and the days or period it covers.
Then add the freshness statement that query_metrics returned, word for word.
"""


def build_agent(model: BaseLlm | str | None = None) -> LlmAgent:
    return LlmAgent(
        name="semantic_agent",
        description="Answers business questions through the dbt semantic layer's metrics.",
        model=model or build_model(),
        generate_content_config=request_config(),
        instruction=INSTRUCTION,
        tools=[FunctionTool(tool) for tool in TOOLS],
        on_model_error_callback=answer_model_failure,
    )


root_agent = build_agent()
