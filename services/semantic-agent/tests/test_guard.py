"""The audit and the freshness survive a swap of the toolset (#177; semantic/PLAN.md SL-4, SL-10).

At work `DataAgentToolset` replaces the metric tools, so these tests build the agent over a
stand-in for it: its data tool has another name, and its calls must still land in the audit and
carry a freshness statement, or say why there is none.
"""

from typing import Any

import pytest
from google.adk.tools import FunctionTool

from semantic_agent import agent as semantic
from tests.conftest import ScriptedLlm, final_text, run_turn

CATALOG = ("list_accessible_data_agents", "get_data_agent_info")
AGENT = "projects/example-project/locations/eu/dataAgents/sales"


def list_accessible_data_agents() -> dict[str, Any]:
    """Lists the data agents this agent may ask."""
    return {"data_agents": [AGENT]}


def get_data_agent_info(data_agent_name: str) -> dict[str, Any]:
    """Describes one data agent."""
    return {"name": data_agent_name, "description": "Sales metrics"}


def toolset(answer: dict[str, Any]) -> list[FunctionTool]:
    """A stand-in for DataAgentToolset whose `ask_data_agent` answers `answer`."""

    def ask_data_agent(data_agent_name: str, question: str) -> dict[str, Any]:
        """Asks a data agent a question; returns its text, rows and SQL."""
        return answer

    return [FunctionTool(f) for f in (list_accessible_data_agents, get_data_agent_info)] + [
        FunctionTool(ask_data_agent)
    ]


ANSWERED = {
    "text": "Revenue was 981.69 EUR on 2026-10-01.",
    "rows": [{"day": "2026-10-01", "revenue_eur": 981.69}],
    "sql": "SELECT SUM(amount_eur) FROM `example-project`.silver.orders",
    "metrics": ["revenue_eur"],
}


def turn(answer: dict[str, Any], catalog_tools=CATALOG) -> tuple[ScriptedLlm, list[Any]]:
    model = ScriptedLlm(
        steps=[
            ("list_accessible_data_agents", {}),
            ("get_data_agent_info", {"data_agent_name": AGENT}),
            ("ask_data_agent", {"data_agent_name": AGENT, "question": "Revenue on 1 Oct?"}),
            "Revenue was 981.69 EUR on 2026-10-01.",
        ]
    )
    agent = semantic.build_agent(model, toolset=toolset(answer), catalog_tools=catalog_tools)
    return model, run_turn(agent, "What was revenue on 1 October 2026?")


def test_a_renamed_data_tool_is_audited_and_its_answer_carries_freshness(audit):
    model, events = turn(ANSWERED)
    results = {r["name"]: r["response"] for r in model.tool_results()}
    statement = results["ask_data_agent"]["freshness"]["statement"]
    assert statement == "Freshness unknown: sales.silver has no ready interval recorded."
    assert "freshness" not in results["get_data_agent_info"]
    (row,) = audit  # the catalog tools read no data
    calls = {c.name: c.id for e in events for c in e.get_function_calls()}
    assert (row["agent"], row["tool"], row["call_id"]) == (
        "semantic_agent",
        "ask_data_agent",
        calls["ask_data_agent"],
    )
    assert row["metrics"] == ["revenue_eur"]
    assert row["sql"] == ANSWERED["sql"]
    assert row["rows_returned"] == 1
    assert row["freshness"] == statement
    assert final_text(events) == "Revenue was 981.69 EUR on 2026-10-01."


def test_an_answer_that_names_no_metrics_says_why_it_has_no_freshness(audit):
    """`ask_data_agent` may not say which metrics it used (docs/semantic-layer-on-bigquery.md)."""
    answer = {key: value for key, value in ANSWERED.items() if key != "metrics"}
    model, _ = turn(answer)
    results = {r["name"]: r["response"] for r in model.tool_results()}
    statement = results["ask_data_agent"]["freshness"]["statement"]
    assert statement == (
        "Freshness unknown: the ask_data_agent result names no metrics, "
        "so their readiness cannot be looked up."
    )
    (row,) = audit
    assert (row["tool"], row["metrics"], row["freshness"]) == ("ask_data_agent", None, statement)


@pytest.mark.parametrize("named", [(), ("list_accessible_data_agents",)])
def test_a_tool_the_seam_does_not_name_as_catalog_is_audited(audit, named):
    """Fail closed: a swap that forgets a catalog tool over-audits it, never skips a data tool."""
    turn(ANSWERED, catalog_tools=named)
    assert {row["tool"] for row in audit} == {
        "list_accessible_data_agents",
        "get_data_agent_info",
        "ask_data_agent",
    } - set(named)
