"""The semantic bet's arm `custom-hybrid` (#373): the semantic agent's MetricFlow tools first,
and a read-only SQL fallback for what no metric answers, its answer then saying so.

It measures the setup the eval's first verdict points at: `custom-metricflow` ties the managed
best where a metric covers the question and loses only where none does (it declines by design),
while the data agents write SQL there. The fallback is the baseline's `execute_sql` over the same
tables and role (`agent_sql`: gold, exposed, the `legacy` schema and, in the bet's fixture,
`silver` and the fiscal calendar (#445), one read-only statement under a timeout). A fallback
answer opens with "Not a governed metric:", a phrase the bet's `hedges` list
holds, so a wrong fallback number is scored wrong (hedged), never confident-wrong, and a right one
counts (docs/research/semantic-bet/RULE.md). Never deployed: the bet's runner builds it in-process
(`python -m semantic_agent.bet_eval --arms custom-hybrid`).
"""

from __future__ import annotations

import functools
from collections.abc import Sequence

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.base_llm import BaseLlm
from google.adk.tools import FunctionTool

from semantic_agent.guard import after_data_tool
from semantic_agent.model import answer_model_failure, build_model, request_config
from semantic_agent.tools import catalog
from semantic_agent.toolset_metricflow import INSTRUCTION as METRICS_FIRST
from semantic_agent.toolset_metricflow import toolset
from sql_baseline.agent import execute_sql, tables

# The two sentences of the metrics-only instruction the fallback replaces: a change to either
# fails here, at import, rather than leaving the hybrid a rule that forbids its own fallback.
NO_SQL = "never compute,\nestimate or recall a figure yourself, and never write SQL."
WITH_SQL = "never compute,\nestimate or recall a figure yourself, except through the fallback."
DECLINE = (
    "If no metric answers the question, say that the semantic layer has no such metric and name "
    "the\nclosest metrics; do not answer from general knowledge."
)
FALLBACK = """\
If no metric answers the question (list_metrics and describe_metric show none that does), fall
back to SQL: write one read-only PostgreSQL query for the execute_sql tool over these tables:
{tables}. Find their columns with information_schema.columns when you need them.
Begin that answer with "Not a governed metric:", then give the figure, the period, and in a few
words how you computed it. Never use SQL for a figure a metric defines, and never answer from
general knowledge."""
for _sentence in (NO_SQL, DECLINE):
    if _sentence not in METRICS_FIRST:
        raise RuntimeError(f"toolset_metricflow.INSTRUCTION changed; hybrid.py needs {_sentence!r}")


def instruction(_context: ReadonlyContext | None = None, extra_tables: Sequence[str] = ()) -> str:
    """The metrics-first instruction with its SQL ban and its decline replaced by the fallback,
    the tables named as the baseline names them, read when the agent first runs."""
    names = ", ".join([*tables(catalog()), *extra_tables])
    return METRICS_FIRST.replace(NO_SQL, WITH_SQL).replace(DECLINE, FALLBACK.format(tables=names))


def build_agent(model: BaseLlm | str | None = None, extra_tables: Sequence[str] = ()) -> LlmAgent:
    """The hybrid: MetricFlow's tools and the baseline's execute_sql, every data call audited."""
    metrics = toolset()
    return LlmAgent(
        name="semantic_hybrid",
        description="Answers through the semantic layer's metrics, with SQL where none covers it.",
        model=model or build_model(),
        generate_content_config=request_config(),
        instruction=functools.partial(instruction, extra_tables=tuple(extra_tables)),
        tools=[*metrics.tools, FunctionTool(execute_sql)],
        after_tool_callback=after_data_tool(metrics.catalog_tools, catalog),
        on_model_error_callback=answer_model_failure,
    )
