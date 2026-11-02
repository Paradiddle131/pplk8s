"""Every answer carries the freshness of its metrics (semantic/PLAN.md SL-4, the lab's D37)."""

import asyncio
import datetime
import uuid

import psycopg
import pytest

from semantic_agent import agent as semantic
from semantic_agent import evaluation, guard, tools
from semantic_agent import freshness as readiness
from semantic_agent.evaluation import FRESHNESS_QUOTED, eval_cases
from semantic_agent.freshness import assess, freshness
from tests.conftest import ScriptedLlm, final_text, run_turn
from tests.test_evaluation import EXPECTED, QUESTIONS, AnswersByQuestion

NOW = datetime.datetime(2026, 10, 29, 12, tzinfo=datetime.UTC)
DAY = datetime.timedelta(days=1)
DEADLINE = datetime.timedelta(hours=36)


def at(day: int) -> datetime.datetime:
    return datetime.datetime(2026, 10, day, tzinfo=datetime.UTC)


def test_a_product_within_its_deadline_is_fresh():
    result = assess([("sales.silver", at(29), DEADLINE)], NOW)
    assert result["late"] is False
    assert result["statement"] == "Fresh: sales.silver is ready up to 2026-10-29T00:00Z."


def test_a_product_past_its_deadline_is_late():
    result = assess([("sales.silver", at(27), DEADLINE)], NOW)
    assert result["late"] is True
    assert result["products"] == [
        {
            "product": "sales.silver",
            "ready_until": "2026-10-27T00:00Z",
            "deadline": "36 h",
            "late": True,
        }
    ]
    assert result["statement"] == (
        "Late: sales.silver is ready only up to 2026-10-27T00:00Z, older than its 36 h deadline."
    )


def test_a_product_with_a_deadline_and_no_ready_row_is_late():
    result = assess([("sales.silver", None, DEADLINE)], NOW)
    assert result["late"] is True
    assert result["statement"] == "Late: sales.silver has never been ready (deadline 36 h)."


def test_a_product_without_a_deadline_or_a_ready_row_is_unknown():
    result = assess([("returns.silver", None, None)], NOW)
    assert result["late"] is False
    assert (
        result["statement"] == "Freshness unknown: returns.silver has no ready interval recorded."
    )


def test_a_product_without_a_deadline_is_never_late():
    result = assess([("returns.silver", at(1), None)], NOW)
    assert result["late"] is False
    assert result["statement"] == "Fresh: returns.silver is ready up to 2026-10-01T00:00Z."


def test_each_product_gets_its_sentence():
    rows = [("returns.silver", at(29), None), ("sales.silver", at(20), DEADLINE)]
    result = assess(rows, NOW)
    assert result["late"] is True
    assert result["statement"].startswith(
        "Fresh: returns.silver is ready up to 2026-10-29T00:00Z. Late:"
    )


def test_an_unreadable_ledger_is_said_not_raised(monkeypatch):
    monkeypatch.setenv("DBT_HOST", "127.0.0.1")
    monkeypatch.setenv("DBT_PORT", "9")
    result = freshness(["sales.silver"])
    assert result["late"] is None
    assert result["statement"].startswith(
        "Freshness unknown: the readiness ledger could not be read"
    )


def test_a_catalog_without_readiness_products_says_so():
    assert freshness([])["statement"].startswith("Freshness unknown: the catalog names no")


@pytest.fixture
def metricflow(monkeypatch):
    monkeypatch.setattr(tools, "run", lambda query, catalog: {"rows": [{"revenue_eur": 868.65}]})
    asked = []

    def stub(products):
        asked.append(products)
        return assess([(p, at(20), DEADLINE) for p in products], NOW)

    monkeypatch.setattr(readiness, "freshness", stub)
    return asked


def test_the_freshness_covers_every_metric_query_metrics_ran(metricflow):
    result = tools.query_metrics(["net_revenue_eur", "revenue_eur"])
    assert result["metrics"] == ["net_revenue_eur", "revenue_eur"]
    assert "freshness" not in result  # the agent's callback attaches it, not the toolset (#177)
    fresh = guard.freshness_of("query_metrics", result["metrics"], tools.catalog())
    assert metricflow == [["returns.silver", "sales.silver"]]
    assert fresh["late"] is True
    assert "Late: returns.silver" in fresh["statement"]


def test_a_failed_query_asks_for_no_freshness(metricflow, monkeypatch):
    def checked(query, catalog):
        query.request(catalog)  # the real run's first step: checks the names against the catalog
        return {"rows": []}

    monkeypatch.setattr(tools, "run", checked)
    model = ScriptedLlm(steps=[("query_metrics", {"metrics": ["average_basket_eur"]}), "none"])
    run_turn(semantic.build_agent(model), "What is the average basket?")
    (result,) = model.tool_results()
    assert "error" in result["response"] and "freshness" not in result["response"]
    assert metricflow == []


def test_the_answer_quotes_the_late_statement_the_tool_returned(metricflow):
    """A scripted model through ADK's Runner: the freshness reaches the model as a tool result."""
    late = "Late: sales.silver is ready only up to 2026-10-20T00:00Z, older than its 36 h deadline."
    model = ScriptedLlm(
        steps=[
            ("query_metrics", {"metrics": ["revenue_eur"], "start_date": "2026-10-02"}),
            f"Revenue was 868.65 EUR on 2 October 2026. {late}",
        ]
    )
    events = run_turn(semantic.build_agent(model), "Revenue on 2 October 2026?")
    (result,) = model.tool_results()
    assert result["response"]["freshness"]["statement"] == late
    assert late in final_text(events)


class Answers(AnswersByQuestion):
    """AnswersByQuestion, quoting the freshness statement when `quote` is set."""

    quote: bool = True

    async def generate_content_async(self, llm_request, stream=False):
        async for response in super().generate_content_async(llm_request, stream):
            statement = next(
                (
                    p.function_response.response["freshness"]["statement"]
                    for c in llm_request.contents
                    for p in c.parts or []
                    if p.function_response and "freshness" in p.function_response.response
                ),
                None,
            )
            part = response.content.parts[0]
            if self.quote and statement and part.text:
                part.text += f" {statement}"
            yield response


@pytest.mark.parametrize(("quote", "score"), [(True, 1.0), (False, 0.0)])
def test_the_eval_scores_whether_the_answer_quotes_its_freshness(metricflow, quote, score):
    cases = eval_cases(QUESTIONS, EXPECTED, "semantic_agent", semantic=True)
    metrics = [evaluation.ANSWER_CORRECT, FRESHNESS_QUOTED]
    agent = semantic.build_agent(Answers(quote=quote))
    outcomes = asyncio.run(evaluation.evaluate(agent, cases, metrics))
    assert outcomes["revenue_one_day"].scores == {"answer_correct": 1.0, "freshness_quoted": score}
    # A question no metric covers has no freshness to quote.
    assert outcomes["amsterdam_temperature"].scores["freshness_quoted"] == 1.0


def test_numbers_in_a_quoted_statement_do_not_make_an_answer_right(metricflow):
    """The statement's deadline (36 h) never passes for an expected 36."""
    expected = {**EXPECTED, "revenue_one_day": [[[36.0]]]}
    cases = eval_cases(QUESTIONS[:1], expected, "semantic_agent", semantic=True)
    agent = semantic.build_agent(Answers())
    outcomes = asyncio.run(evaluation.evaluate(agent, cases, [evaluation.ANSWER_CORRECT]))
    assert outcomes["revenue_one_day"].scores == {"answer_correct": 0.0}


WAREHOUSE_OWNER = "postgresql://warehouse:warehouse@localhost:5433/warehouse"


@pytest.fixture
def ledger(monkeypatch):
    """Readiness rows of throwaway sales layers in the Compose warehouse; read as agent_metrics."""
    for name, value in {
        "DBT_HOST": "localhost",
        "DBT_PORT": "5433",
        "DBT_DBNAME": "warehouse",
        "DBT_USER": "agent_metrics",
        "DBT_PASSWORD": "agent_metrics",
    }.items():
        monkeypatch.setenv(name, value)
    tag = uuid.uuid4().hex[:8]
    fresh, late = f"sales.test_fresh_{tag}", f"sales.test_late_{tag}"
    now = datetime.datetime.now(datetime.UTC)
    try:
        owner = psycopg.connect(WAREHOUSE_OWNER, connect_timeout=3, autocommit=True)
    except psycopg.Error as e:
        from tests.conftest import service_unreachable

        service_unreachable("the warehouse", e)
    with owner:
        owner.execute(
            "insert into ops.readiness (product, interval_start, interval_end, run_id, status) "
            "values (%s, %s, %s, 'test', 'ready'), (%s, %s, %s, 'test', 'ready'), "
            "(%s, %s, %s, 'test', 'failed')",
            (
                fresh, now - 2 * DAY, now - datetime.timedelta(hours=1),
                late, now - 3 * DAY, now - 2 * DAY,
                late, now - 2 * DAY, now - datetime.timedelta(hours=1),
            ),
        )  # fmt: skip
        try:
            yield fresh, late, tag
        finally:
            owner.execute(
                "delete from ops.readiness where product like %s", (f"sales.test_%_{tag}",)
            )


def test_the_ledger_is_read_as_agent_metrics_with_the_pipeline_deadline(ledger):
    fresh, late, tag = ledger
    result = freshness([fresh, late, f"nosuch_{tag}.silver"])
    by_product = {p["product"]: p for p in result["products"]}
    assert by_product[fresh]["late"] is False and by_product[fresh]["deadline"] == "36 h"
    assert by_product[late]["late"] is True  # its newer interval failed: not ready
    assert by_product[f"nosuch_{tag}.silver"] == {
        "product": f"nosuch_{tag}.silver",
        "ready_until": None,
        "deadline": None,
        "late": False,
    }
    assert result["late"] is True


def test_agent_metrics_reads_no_other_ops_table(ledger):
    with (
        psycopg.connect(
            "postgresql://agent_metrics:agent_metrics@localhost:5433/warehouse"
        ) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute("select * from ops.file_loads")
