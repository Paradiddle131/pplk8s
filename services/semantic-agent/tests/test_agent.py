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


def test_list_metrics_also_gives_the_glossary_of_terms_that_are_not_metrics():
    listed = tools.list_metrics()
    terms = {term["term"]: term for term in listed["glossary"]}
    assert terms["Signup cohort"]["dimensions"] == ["customer__signup_date"]
    assert "Signup cohort" not in {metric["label"] for metric in listed["metrics"]}
    metrics = {metric["name"] for metric in listed["metrics"]}
    assert all(set(term["metrics"]) <= metrics for term in terms.values())


def test_list_metrics_also_gives_the_saved_queries_with_their_questions():
    listed = {query["name"]: query for query in tools.list_metrics()["saved_queries"]}
    assert listed["orders_by_status"] == {
        "name": "orders_by_status",
        "question": "How many orders are there in each status?",
        "metrics": ["orders_total"],
        "group_by": ["order__status"],
        "where": [],
    }


def test_a_saved_query_runs_through_query_metrics_with_its_metrics_freshness(metricflow, audit):
    """Issue #164: the model names a saved query; its metrics give the freshness and the audit."""
    args = {"saved_query": "net_sales_daily", "start_date": "2026-10-01", "end_date": "2026-10-01"}
    model = ScriptedLlm(steps=[("query_metrics", args), "Net revenue was 981.69 EUR."])
    run_turn(semantic.build_agent(model), "What were revenue, returns and net revenue on 1 Oct?")
    (request,) = metricflow
    assert request.saved_query_name == "net_sales_daily"
    (result,) = model.tool_results()
    assert result["response"]["metrics"] == [
        "revenue_eur",
        "returns_count",
        "returns_eur",
        "net_revenue_eur",
    ]
    assert "returns.silver" in result["response"]["freshness"]["statement"]
    assert "sales.silver" in result["response"]["freshness"]["statement"]
    (row,) = audit
    assert row["metrics"] == result["response"]["metrics"]
    assert row["arguments"] == args


def test_filters_from_the_model_reach_metricflow_as_checked_literals(metricflow):
    args = {
        "metrics": ["orders_total"],
        # A dimension that declares no values passes any value on, as a quoted literal.
        "filters": [{"dimension": "order__currency", "values": ["EUR'; drop table x; --"]}],
    }
    run_turn(semantic.build_agent(ScriptedLlm(steps=[("query_metrics", args), "done"])), "q")
    assert metricflow[0].where_constraints == [
        "{{ Dimension('order__currency') }} = 'EUR''; drop table x; --'"
    ]


def test_a_templated_filter_value_comes_back_as_an_error_and_never_reaches_metricflow(metricflow):
    """Issue #161: a value is compared as the text the model sent, or refused."""
    args = {
        "metrics": ["orders_total"],
        "filters": [{"dimension": "order__currency", "values": ["{{ 7*7 }}"]}],
    }
    model = ScriptedLlm(steps=[("query_metrics", args), "No such currency."])
    run_turn(semantic.build_agent(model), "Orders in currency {{ 7*7 }}?")
    (refused,) = model.tool_results()
    assert "'{{ 7*7 }}'" in refused["response"]["error"]
    assert "template delimiter" in refused["response"]["error"]
    assert metricflow == []


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


def test_a_guessed_filter_value_comes_back_with_the_known_ones_and_the_model_retries(metricflow):
    """Issue #157: "damaged goods" matched no row and was answered as a confident zero."""
    guessed = {"dimension": "return__reason", "operator": "=", "values": ["damaged goods"]}
    known = {**guessed, "values": ["damaged"]}
    model = ScriptedLlm(
        steps=[
            ("describe_metric", {"name": "returns_eur"}),
            ("query_metrics", {"metrics": ["returns_eur"], "filters": [guessed]}),
            ("query_metrics", {"metrics": ["returns_eur"], "filters": [known]}),
            "Returns of damaged goods cost 12.5 EUR.",
        ]
    )
    run_turn(semantic.build_agent(model), "How much did returns of damaged goods cost us?")
    described, refused, answered = model.tool_results()
    reason = next(d for d in described["response"]["dimensions"] if d["name"] == "return__reason")
    assert "damaged" in reason["values"]
    assert "'return__reason' has no value 'damaged goods'" in refused["response"]["error"]
    assert "'damaged'" in refused["response"]["error"]
    assert "error" not in answered["response"]
    assert [r.where_constraints for r in metricflow] == [
        ["{{ Dimension('return__reason') }} = 'damaged'"]
    ]


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


def test_the_baseline_is_told_every_public_model_of_the_catalog():
    """Issue #162: a hand-written list had dropped the marketing tables, so the baseline lost by
    configuration rather than by its pattern."""
    told = baseline.instruction()
    relations = [model["relation"] for model in tools.catalog().models]
    assert len(relations) == 12
    for relation in relations:
        schema, table = relation.split(".")[-2:]
        assert f"{schema}.{table}" in told, f"{relation} is missing from the baseline's tables"
    assert "gold.marketing_daily" in told
    assert "exposed.channel_performance_daily" in told
    assert "gold.customer_engagement_daily" in told


def test_a_question_reaches_the_baseline_with_the_catalog_tables():
    model = ScriptedLlm(steps=["No SQL needed."])
    run_turn(baseline.build_agent(model), "Which tables do you know?")
    system = model.requests[0].config.system_instruction
    assert "gold.marketing_daily" in str(system)


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
