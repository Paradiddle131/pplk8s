"""The audit and the freshness survive a swap of the toolset (#177, #207; semantic/PLAN.md SL-10).

`AGENT_TOOLSET=data_agent` replaces the metric tools with ADK's `DataAgentToolset`, so these tests
build the agent over a stand-in for it carrying its documented tool names and `ask_data_agent`'s
documented result (steps, one with the generated SQL, one with the rows): its calls must still land
in the audit and carry a freshness statement, looked up from the tables the SQL reads, or say why
there is none.
"""

import asyncio
import os
import subprocess
import sys
from typing import Any

import pytest
from google.adk.tools import FunctionTool

from semantic_agent import agent as semantic
from semantic_agent import audit as auditing
from semantic_agent.metrics import Catalog
from semantic_agent.toolset import Toolset, toolset
from tests.conftest import FIXTURES, ScriptedLlm, final_text, run_turn

CATALOG = ("list_accessible_data_agents", "get_data_agent_info")
AGENT = "projects/example-project/locations/us/dataAgents/pplk8s-semantic"
SQL = (
    "SELECT\n  SUM(orders.amount_eur) AS revenue_eur\nFROM\n  `example-project.silver.orders`"
    " AS orders\nWHERE\n  orders.ordered_at >= '2026-10-01'"
)


def list_accessible_data_agents() -> dict[str, Any]:
    """Lists the data agents this agent may ask."""
    return {"status": "SUCCESS", "response": [{"name": AGENT}]}


def get_data_agent_info(data_agent_name: str) -> dict[str, Any]:
    """Describes one data agent."""
    return {"status": "SUCCESS", "response": {"name": data_agent_name}}


def stand_in(answer: dict[str, Any]) -> list[FunctionTool]:
    """A stand-in for DataAgentToolset whose `ask_data_agent` answers `answer`."""

    def ask_data_agent(data_agent_name: str, query: str) -> dict[str, Any]:
        """Asks a data agent a question; returns its steps: thoughts, SQL, rows, answer."""
        return answer

    return [FunctionTool(f) for f in (list_accessible_data_agents, get_data_agent_info)] + [
        FunctionTool(ask_data_agent)
    ]


def answer(sql: str = SQL) -> dict[str, Any]:
    """`ask_data_agent`'s documented result (ADK 2.13's docstring): its steps, no metric names."""
    return {
        "status": "SUCCESS",
        "response": [
            {"text": {"parts": ["Retrieved context for 1 table."], "textType": "THOUGHT"}},
            {"data": {"generatedSql": sql}},
            {
                "Data Retrieved": {
                    "headers": ["revenue_eur"],
                    "rows": [[981.69]],
                    "summary": "Showing all 1 rows.",
                }
            },
            {"text": {"parts": ["Revenue was 981.69 EUR."], "textType": "FINAL_RESPONSE"}},
        ],
    }


def turn(result: dict[str, Any], catalog_tools=CATALOG) -> tuple[ScriptedLlm, list[Any]]:
    model = ScriptedLlm(
        steps=[
            ("list_accessible_data_agents", {}),
            ("get_data_agent_info", {"data_agent_name": AGENT}),
            ("ask_data_agent", {"data_agent_name": AGENT, "query": "Revenue on 1 Oct?"}),
            "Revenue was 981.69 EUR on 2026-10-01.",
        ]
    )
    tools = Toolset(tools=stand_in(result), catalog_tools=catalog_tools, instruction="Answer.")
    return model, run_turn(semantic.build_agent(model, tools), "Revenue on 1 October 2026?")


def test_a_data_agents_answer_is_audited_and_its_tables_give_its_freshness(audit):
    model, events = turn(answer())
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
    assert row["metrics"] is None
    assert row["sql"] == SQL
    assert row["rows_returned"] == 1
    assert row["freshness"] == statement
    assert final_text(events) == "Revenue was 981.69 EUR on 2026-10-01."


def test_an_answer_that_reads_no_semantic_models_table_says_why_it_has_no_freshness(audit):
    """`ask_data_agent` names no metrics (docs/semantic-layer-on-bigquery.md), and this SQL reads
    a table no semantic model reads, so there is nothing to look up."""
    model, _ = turn(answer("SELECT COUNT(*) FROM `example-project.legacy.orders_v1`"))
    results = {r["name"]: r["response"] for r in model.tool_results()}
    statement = results["ask_data_agent"]["freshness"]["statement"]
    assert statement == (
        "Freshness unknown: the ask_data_agent result names no metrics and reads no semantic "
        "model's table, so their readiness cannot be looked up."
    )
    (row,) = audit
    assert (row["tool"], row["metrics"], row["freshness"]) == ("ask_data_agent", None, statement)


def test_a_result_that_names_metrics_is_looked_up_by_them():
    """MetricFlow's result names its metrics; a data agent's names tables: both find the ledger."""
    from semantic_agent.guard import freshness_of

    catalog = Catalog.load(FIXTURES / "agent.json")
    by_metric = freshness_of("query_metrics", ["revenue_eur"], catalog)
    by_table = freshness_of("ask_data_agent", [], catalog, tables=["p.silver.orders"])
    assert [p["product"] for p in by_metric["products"]] == ["sales.silver"]
    assert by_table["products"] == by_metric["products"]


def test_a_data_agent_error_is_audited_as_an_error_and_given_no_freshness(audit):
    model, _ = turn({"status": "ERROR", "error_details": "403 Permission denied"})
    results = {r["name"]: r["response"] for r in model.tool_results()}
    assert "freshness" not in results["ask_data_agent"]
    (row,) = audit
    assert (row["error"], row["sql"]) == ("403 Permission denied", None)


@pytest.mark.parametrize("named", [(), ("list_accessible_data_agents",)])
def test_a_tool_the_seam_does_not_name_as_catalog_is_audited(audit, named):
    """Fail closed: a swap that forgets a catalog tool over-audits it, never skips a data tool."""
    turn(answer(), catalog_tools=named)
    assert {row["tool"] for row in audit} == {
        "list_accessible_data_agents",
        "get_data_agent_info",
        "ask_data_agent",
    } - set(named)


# The tables generated SQL reads.


@pytest.mark.parametrize(
    ("sql", "tables"),
    [
        (SQL, ["example-project.silver.orders"]),
        ("select 1 from `p`.`silver`.`orders` o join silver.returns r on o.id = r.id", None),
        ("SELECT * FROM `p.silver.orders`, UNNEST(items)", ["p.silver.orders"]),
        ("WITH t AS (SELECT * FROM p.gold.revenue) SELECT * FROM t", ["p.gold.revenue"]),
        ("SELECT * FROM (SELECT 1)", []),
    ],
)
def test_tables_read_finds_every_qualified_table(sql, tables):
    expected = tables if tables is not None else ["p.silver.orders", "silver.returns"]
    assert auditing.tables_read([sql]) == expected


def test_semantic_models_tables_map_to_their_readiness_whatever_the_project():
    catalog = Catalog.load(FIXTURES / "agent.json")
    assert catalog.readiness_of_tables(["lab-project.silver.orders", "SILVER.ad_spend"]) == [
        "marketing.silver",
        "sales.silver",
    ]
    assert catalog.readiness_of_tables(["lab-project.legacy.orders_v1", "orders"]) == []


# The seam.


def test_metricflow_is_the_default_toolset(monkeypatch):
    monkeypatch.delenv("AGENT_TOOLSET", raising=False)
    chosen = toolset()
    assert [t.name for t in chosen.tools] == ["list_metrics", "describe_metric", "query_metrics"]
    assert chosen.catalog_tools == ("list_metrics", "describe_metric")


def test_an_unknown_toolset_is_refused(monkeypatch):
    monkeypatch.setenv("AGENT_TOOLSET", "langchain")
    with pytest.raises(ValueError, match="AGENT_TOOLSET='langchain' is not one of"):
        toolset()


def test_the_data_agent_toolset_refuses_without_a_project(monkeypatch):
    monkeypatch.setenv("AGENT_TOOLSET", "data_agent")
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("DATA_AGENT_NAME", raising=False)
    with pytest.raises(ValueError, match="needs DATA_AGENT_NAME or GCP_PROJECT"):
        toolset()


def test_the_data_agent_toolset_asks_the_lab_projects_agent(monkeypatch):
    monkeypatch.setenv("AGENT_TOOLSET", "data_agent")
    monkeypatch.setenv("GCP_PROJECT", "lab-project")
    monkeypatch.setenv("GCP_ACCESS_TOKEN", "placeholder-replaced-by-the-proxy")
    chosen = toolset()
    (data_agents,) = chosen.tools
    names = [tool.name for tool in asyncio.run(data_agents.get_tools())]
    assert names == ["get_data_agent_info", "ask_data_agent"]
    assert "projects/lab-project/locations/us/dataAgents/pplk8s-semantic" in chosen.instruction
    assert set(names) - set(chosen.catalog_tools) == {"ask_data_agent"}


def test_the_served_agent_builds_over_the_data_agent():
    """`adk api_server` imports root_agent with AGENT_TOOLSET=data_agent, as the eval's arm does,
    and never imports MetricFlow's toolset module."""
    code = (
        "import sys, semantic_agent\n"
        "print(semantic_agent.agent.root_agent.instruction.splitlines()[0])\n"
        "print('semantic_agent.toolset_metricflow' in sys.modules)\n"
    )
    env = {
        **os.environ,
        "AGENT_TOOLSET": "data_agent",
        "GCP_PROJECT": "lab-project",
        "GCP_ACCESS_TOKEN": "placeholder",
    }
    out = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    first, metricflow = out.stdout.splitlines()
    assert "projects/lab-project/locations/us/dataAgents/pplk8s-semantic" in first
    assert metricflow == "False"
