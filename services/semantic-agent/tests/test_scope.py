"""The row scope reaches the answer and the audit (semantic/PLAN.md SL-21).

The warehouse enforces the scope; these tests check what the agent says about it, without a
warehouse: `scope.lookup` stands in for the role's row of ops.agent_scopes.
"""

from typing import Any

import pytest
from google.adk.tools import FunctionTool

from semantic_agent import agent as semantic
from semantic_agent import scope
from tests.conftest import ScriptedLlm, run_turn

SCOPED = ["silver.customers", "silver.orders", "silver.returns"]
# MetricFlow's SQL on Postgres names a table with its database, quoted or not.
ORDERS_SQL = 'SELECT SUM(amount) FROM "dbt_dev"."silver"."orders" orders_src_10000'
LEADS_SQL = "SELECT COUNT(*) FROM dbt_dev.silver.leads leads_src_10000"


@pytest.mark.parametrize(
    ("sql", "read"),
    [
        (ORDERS_SQL, ["silver.orders"]),
        ("select 1 from silver.orders o join silver.customers c using (customer_id)",
         ["silver.customers", "silver.orders"]),
        (LEADS_SQL, []),
        # A longer name that starts with a scoped one is another table.
        ("select 1 from silver.orders_daily", []),
        ('select 1 from "silver"."returns"', ["silver.returns"]),
    ],
)  # fmt: skip
def test_tables_read_finds_the_scoped_tables_a_query_names(sql: str, read: list[str]) -> None:
    assert scope.tables_read(sql, SCOPED) == read


def test_an_unscoped_role_gets_no_scope() -> None:
    assert scope.assess(None, SCOPED, ORDERS_SQL) is None


def test_a_scoped_figure_says_whose_rows_it_counted() -> None:
    found = scope.assess(["DE"], SCOPED, ORDERS_SQL)
    assert found is not None and found["read"] == ["silver.orders"]
    assert found["statement"] == (
        "Scoped: this figure counts only customers in DE (silver.orders), the rows this agent "
        "may read, not the whole company."
    )


def test_a_figure_from_unscoped_tables_says_it_covers_every_country() -> None:
    found = scope.assess(["DE"], SCOPED, LEADS_SQL)
    assert found is not None and found["statement"].startswith("Not scoped:")


def test_a_result_without_its_sql_says_the_scope_is_unknown() -> None:
    found = scope.assess(["DE"], SCOPED, None)
    assert found is not None and found["statement"].startswith("Scope unknown:")


def test_an_unreadable_scope_is_said_not_raised(monkeypatch) -> None:
    import psycopg

    def broken() -> Any:
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(scope, "lookup", broken)
    found = scope.scope(ORDERS_SQL)
    assert found is not None and found["statement"].startswith(
        "Scope unknown: the agent's row scope could not be read (connection refused)"
    )


def test_the_semantic_agent_passes_the_scope_to_the_model_and_the_audit(monkeypatch, audit):
    monkeypatch.setattr(scope, "lookup", lambda: (["DE"], SCOPED))

    def query_metrics(metrics: list[str]) -> dict[str, Any]:
        """Queries metrics."""
        return {"metrics": metrics, "rows": [{"revenue_eur": 312.5}], "sql": ORDERS_SQL}

    model = ScriptedLlm(
        steps=[("query_metrics", {"metrics": ["revenue_eur"]}), "Revenue was 312.5 EUR."]
    )
    agent = semantic.build_agent(model, toolset=[FunctionTool(query_metrics)], catalog_tools=())
    run_turn(agent, "What was revenue?")
    [shown] = model.tool_results()
    result = shown["response"]
    assert result["scope"]["statement"].startswith("Scoped: this figure counts only customers in DE")
    [row] = audit
    assert row["scope"] == result["scope"]["statement"]
    assert "scope statement word for word" in agent.instruction


def test_the_baseline_reads_no_scope(monkeypatch, audit):
    """The text-to-SQL baseline gets no catalog, so no freshness and no scope: its role is not a
    metric reader's."""
    called = []
    monkeypatch.setattr(scope, "lookup", lambda: called.append(1) or (["DE"], SCOPED))
    from semantic_agent.audit import Caller
    from semantic_agent.guard import guarded

    shown = guarded("execute_sql", {"sql": "select 1"}, {"rows": []}, Caller(agent="x"))
    assert "scope" not in shown and not called
