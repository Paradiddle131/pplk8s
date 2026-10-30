"""The semantic agent's loop with a scripted model, through ADK's own Runner (no live model)."""

import inspect

import pytest

from semantic_agent import agent as semantic
from semantic_agent import tools
from semantic_agent.model import build_model
from sql_baseline import agent as baseline
from tests.conftest import ScriptedLlm, final_text, run_turn

ROWS = {
    "columns": ["metric_time__day", "revenue_eur"],
    "rows": [{"metric_time__day": "2026-10-01", "revenue_eur": 981.69}],
    "row_count": 1,
    "sql": "SELECT ...",
}


@pytest.fixture
def metricflow(monkeypatch):
    """MetricFlow stubbed at its seam: records each query, answers ROWS."""
    calls = []

    def run(query, catalog):
        calls.append(query.request(catalog))
        return ROWS

    monkeypatch.setattr(tools, "run", run)
    return calls


def test_the_semantic_agent_has_only_the_three_metric_tools():
    names = [t.name for t in semantic.build_agent(ScriptedLlm()).tools]
    assert names == ["list_metrics", "describe_metric", "query_metrics"]
    for tool in tools.TOOLS:
        assert not {"sql", "query", "statement"} & inspect.signature(tool).parameters.keys()


def test_a_question_is_answered_from_query_metrics(metricflow):
    model = ScriptedLlm(
        steps=[
            ("list_metrics", {}),
            ("query_metrics", {"metrics": ["revenue_eur"], "group_by": ["metric_time__day"]}),
            "Revenue was 981.69 EUR on 2026-10-01.",
        ]
    )
    events = run_turn(semantic.build_agent(model), "What was revenue by day?")
    assert final_text(events) == "Revenue was 981.69 EUR on 2026-10-01."
    assert [r.metric_names for r in metricflow] == [["revenue_eur"]]
    results = model.tool_results()
    assert [r["name"] for r in results] == ["list_metrics", "query_metrics"]
    listed = {m["name"] for m in results[0]["response"]["metrics"]}
    assert "net_revenue_eur" in listed
    assert results[1]["response"]["rows"] == ROWS["rows"]


def test_filters_from_the_model_reach_metricflow_as_checked_literals(metricflow):
    args = {
        "metrics": ["orders_total"],
        "filters": [{"dimension": "order__status", "values": ["cancelled'; drop table x; --"]}],
    }
    run_turn(semantic.build_agent(ScriptedLlm(steps=[("query_metrics", args), "done"])), "q")
    assert metricflow[0].where_constraints == [
        "{{ Dimension('order__status') }} = 'cancelled''; drop table x; --'"
    ]


def test_a_metric_the_catalog_lacks_comes_back_as_an_error_to_the_model(metricflow):
    model = ScriptedLlm(
        steps=[
            ("describe_metric", {"name": "average_basket_eur"}),
            ("query_metrics", {"metrics": ["average_basket_eur"]}),
            "The semantic layer has no metric for average basket size.",
        ]
    )
    events = run_turn(semantic.build_agent(model), "What is the average basket?")
    described, queried = model.tool_results()
    assert "no metric named 'average_basket_eur'" in described["response"]["error"]
    assert "no metric named 'average_basket_eur'" in queried["response"]["error"]
    assert metricflow == []
    assert "no metric" in final_text(events)


def test_the_semantic_agent_cannot_run_sql(metricflow, monkeypatch):
    """A model that reaches for an SQL tool gets no such tool: nothing runs on the warehouse."""
    executed = []
    monkeypatch.setattr(baseline, "execute_sql", lambda sql: executed.append(sql))
    model = ScriptedLlm(steps=[("execute_sql", {"sql": "select 1"}), "I cannot run SQL."])
    run_turn(semantic.build_agent(model), "Run select 1")
    (result,) = model.tool_results()
    assert result["name"] == "execute_sql"
    assert "no tool with that name" in result["response"]["error"]  # ADK's own refusal
    assert executed == []
    assert metricflow == []


def test_the_baseline_has_only_execute_sql():
    assert [t.name for t in baseline.build_agent(ScriptedLlm()).tools] == ["execute_sql"]


@pytest.mark.parametrize(
    ("backend", "model_id"), [("openrouter", "some/model:free"), ("gemini", "some-model")]
)
def test_the_model_seam_builds_each_backend(backend, model_id):
    model = build_model(backend, model_id)
    assert model.model.endswith(model_id)


@pytest.mark.parametrize(
    "model_id", ["anthropic/claude-sonnet-4.5", "some/model:free-ish", "some/model"]
)
def test_the_model_seam_refuses_a_paid_openrouter_model(model_id):
    with pytest.raises(ValueError, match=":free"):
        build_model("openrouter", model_id)


def test_the_model_seam_refuses_an_unknown_backend():
    with pytest.raises(ValueError, match="MODEL_BACKEND"):
        build_model("ollama", "x")
