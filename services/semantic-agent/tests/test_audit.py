"""Every data query either agent runs leaves one audit row (scripted model, no warehouse)."""

import pytest

from semantic_agent import agent as semantic
from semantic_agent import audit, tools
from semantic_agent.warehouse import WarehouseError
from sql_baseline import agent as baseline
from tests.conftest import ScriptedLlm, final_text, run_turn

ROWS = {
    "columns": ["metric_time__day", "orders_total"],
    "rows": [{"metric_time__day": "2026-10-01", "orders_total": 3}],
    "row_count": 1,
    "sql": "SELECT compiled_by_metricflow",
}
QUERY = {
    "metrics": ["orders_total"],
    "group_by": ["metric_time__day"],
    "filters": [{"dimension": "order__status", "operator": "=", "values": ["cancelled"]}],
    "start_date": "2026-10-01",
    "end_date": "2026-10-02",
}


@pytest.fixture
def metricflow(monkeypatch):
    def run(query, catalog):
        query.request(catalog)  # refuses a metric the catalog lacks, as MetricFlow's run does
        return ROWS

    monkeypatch.setattr(tools, "run", run)


def test_a_metric_query_leaves_one_row_with_who_asked_what_and_what_came_back(metricflow, audit):
    model = ScriptedLlm(
        steps=[
            ("list_metrics", {}),
            ("describe_metric", {"name": "orders_total"}),
            ("query_metrics", QUERY),
            "3 cancelled orders on 2026-10-01.",
        ]
    )
    events = run_turn(semantic.build_agent(model), "How many cancelled orders?")
    (row,) = audit  # listing and describing metrics read only the catalog
    calls = {c.name: c.id for e in events for c in e.get_function_calls()}
    assert row["agent"] == "semantic_agent"
    assert row["tool"] == "query_metrics"
    assert row["user_id"] == "u"
    assert row["session_id"]
    assert row["invocation_id"] == events[-1].invocation_id
    assert row["call_id"] == calls["query_metrics"]
    assert row["metrics"] == ["orders_total"]
    assert row["filters"] == QUERY["filters"]
    assert row["arguments"] == QUERY
    assert row["sql"] == "SELECT compiled_by_metricflow"
    assert row["rows_returned"] == 1
    assert row["freshness"].startswith("Freshness unknown: sales.silver")
    assert row["error"] is None


def test_a_refused_metric_query_is_audited_with_its_error(metricflow, audit):
    model = ScriptedLlm(steps=[("query_metrics", {"metrics": ["average_basket_eur"]}), "none"])
    run_turn(semantic.build_agent(model), "What is the average basket?")
    (row,) = audit
    assert "no metric named 'average_basket_eur'" in row["error"]
    assert row["rows_returned"] is None
    assert row["sql"] is None


def test_the_baselines_sql_is_audited_as_the_model_wrote_it(monkeypatch, audit):
    def execute_sql(sql: str) -> dict:
        return {"columns": ["n"], "rows": [{"n": 3}, {"n": 4}], "truncated": False}

    monkeypatch.setattr(baseline, "execute_sql", execute_sql)
    sql = "select count(*) as n from gold.daily_sales"
    model = ScriptedLlm(steps=[("execute_sql", {"sql": sql}), "3"])
    run_turn(baseline.build_agent(model), "How many days?")
    (row,) = audit
    assert (row["agent"], row["tool"], row["sql"], row["rows_returned"]) == (
        "sql_baseline",
        "execute_sql",
        sql,
        2,
    )
    assert row["metrics"] is None and row["freshness"] is None


def test_an_unwritable_audit_withholds_the_rows(metricflow, monkeypatch):
    def refuse(row):
        raise WarehouseError("connection refused")

    monkeypatch.setattr(audit, "record", refuse)
    model = ScriptedLlm(steps=[("query_metrics", QUERY), "The answer is unavailable."])
    events = run_turn(semantic.build_agent(model), "How many cancelled orders?")
    (result,) = model.tool_results()
    assert "rows" not in result["response"]
    assert "audit row could not be written (connection refused)" in result["response"]["error"]
    assert final_text(events) == "The answer is unavailable."
