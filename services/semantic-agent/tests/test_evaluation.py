"""The eval driver on ADK's LocalEvalService with a scripted model: no warehouse, no live model."""

import asyncio

import pytest

from semantic_agent import agent as semantic
from semantic_agent import evaluation, tools
from semantic_agent.evaluation import (
    ANSWER_CORRECT,
    METRIC_CHOICE,
    Question,
    as_expected,
    carries,
    eval_cases,
    load_questions,
    numbers_in,
)
from tests.conftest import ScriptedLlm


def test_the_question_set_is_about_fifty_with_some_no_metric_covers():
    # Each domain and each question shape adds its questions (semantic/PLAN.md SL-5, SL-14);
    # the bound keeps a live run's free-tier calls in check.
    questions = load_questions()
    assert 30 <= len(questions) <= 60
    assert len({q.id for q in questions}) == len(questions)
    assert any(not q.metrics for q in questions)
    known = set(tools.catalog().metrics)
    assert all(set(q.metrics) <= known for q in questions)


@pytest.mark.parametrize(
    ("text", "numbers"),
    [
        ("Revenue was 1,850.34 EUR over 1 and 2 October 2026.", [1850.34]),
        ("On 2026-10-02 there were 9 customers.", [9.0]),
        ("Net revenue on October 1, 2026 was €964.19.", [964.19]),
        ("16.67% of orders in October 2026 were cancelled", [16.67]),
    ],
)
def test_numbers_in_an_answer_leave_dates_out(text, numbers):
    assert numbers_in(text) == numbers


@pytest.mark.parametrize(
    "answer",
    [
        "The semantic layer has no such metric for weather.",
        "The semantic layer has no revenue metric that can be filtered by customer country, "
        "so I can't give a Germany-specific figure.",
        "I cannot answer the weather question from this data.",
    ],
)
def test_declines_are_recognised(answer):
    assert evaluation.DECLINE.search(answer)


def test_an_answer_is_not_a_decline():
    assert not evaluation.DECLINE.search("Revenue was 981.69 EUR on 1 October 2026.")


def test_a_rate_is_expected_as_a_percentage_rounded_only_once():
    # 0.3265327... is 32.65 % at two decimals and 32.7 % at one; a percentage kept at two decimals
    # and rounded again to one gives 32.6 (32.65 is 32.6499... as a float).
    assert carries("Revenue grew by 32.7%", as_expected(0.3265327921384320))
    assert carries("32.65 %", as_expected(0.3265327921384320))
    assert not carries("32.6%", as_expected(0.3265327921384320))
    assert as_expected(964.19) == [964.19]


def test_an_answer_carries_a_number_within_rounding():
    assert carries("about 0.1667 of orders", [0.16666666, 16.67])
    assert carries("16.7%", [0.16666666, 16.67])  # rounded to the decimals it states
    assert not carries("17%", [0.16666666, 16.67])
    assert carries("964.19 EUR", [964.19])
    assert not carries("965 EUR", [964.19])


QUESTIONS = [
    Question("revenue_one_day", "Revenue on 2 October 2026?", "", ["revenue_eur"]),
    Question("amsterdam_temperature", "Temperature in Amsterdam?", "", []),
]
EXPECTED = {"revenue_one_day": [868.65], "amsterdam_temperature": [11.0]}


class AnswersByQuestion(ScriptedLlm):
    """Queries revenue for the revenue question, then answers; declines the weather question."""

    async def generate_content_async(self, llm_request, stream=False):
        question = llm_request.contents[0].parts[0].text
        answered = any(p.function_response for c in llm_request.contents for p in c.parts or [])
        if "Revenue" in question and not answered:
            self.steps = [("query_metrics", {"metrics": ["revenue_eur"]})]
        elif "Revenue" in question:
            self.steps = ["Revenue was 868.65 EUR on 2 October 2026."]
        else:
            self.steps = ["The semantic layer has no metric for temperature."]
        self.requests = []
        async for response in super().generate_content_async(llm_request, stream):
            yield response


def test_the_driver_scores_answers_and_metric_choice(monkeypatch):
    monkeypatch.setattr(tools, "run", lambda query, catalog: {"rows": [{"revenue_eur": 868.65}]})
    cases = eval_cases(QUESTIONS, EXPECTED, "semantic_agent", semantic=True)
    outcomes = asyncio.run(
        evaluation.evaluate(
            semantic.build_agent(AnswersByQuestion()), cases, [ANSWER_CORRECT, METRIC_CHOICE]
        )
    )
    assert outcomes["revenue_one_day"].scores == {"answer_correct": 1.0, "metric_choice": 1.0}
    assert outcomes["amsterdam_temperature"].scores["answer_correct"] == 1.0
    text = evaluation.report(QUESTIONS, EXPECTED, outcomes, {}, "scripted")
    assert (
        "| Questions a metric covers (1) | 1 right, 1 with the expected metric, "
        "0 quoting their freshness | 0 right |" in text
    )
    assert "| Questions no metric covers (1) | 1 said so | 0 right |" in text


class RunsASavedQuery(ScriptedLlm):
    """Answers the revenue question through the daily_sales saved query (#164)."""

    async def generate_content_async(self, llm_request, stream=False):
        answered = any(p.function_response for c in llm_request.contents for p in c.parts or [])
        self.steps = (
            ["Revenue was 868.65 EUR on 2 October 2026."]
            if answered
            else [("query_metrics", {"saved_query": "daily_sales", "start_date": "2026-10-02"})]
        )
        self.requests = []
        async for response in super().generate_content_async(llm_request, stream):
            yield response


def test_a_saved_query_counts_as_querying_its_metrics(monkeypatch):
    monkeypatch.setattr(tools, "run", lambda query, catalog: {"rows": [{"revenue_eur": 868.65}]})
    cases = eval_cases(QUESTIONS[:1], EXPECTED, "semantic_agent", semantic=True)
    outcomes = asyncio.run(
        evaluation.evaluate(
            semantic.build_agent(RunsASavedQuery()), cases, [ANSWER_CORRECT, METRIC_CHOICE]
        )
    )
    assert outcomes["revenue_one_day"].scores == {"answer_correct": 1.0, "metric_choice": 1.0}


def test_a_wrong_number_or_an_answer_where_it_should_decline_fails(monkeypatch):
    monkeypatch.setattr(tools, "run", lambda query, catalog: {"rows": []})
    cases = eval_cases(QUESTIONS, EXPECTED, "semantic_agent", semantic=True)
    model = ScriptedLlm(steps=["It was 900 EUR and 11 degrees."] * 2)

    class EveryTurn(ScriptedLlm):
        async def generate_content_async(self, llm_request, stream=False):
            self.requests = []
            async for response in model.generate_content_async(llm_request, stream):
                model.requests = []
                yield response

    outcomes = asyncio.run(
        evaluation.evaluate(
            semantic.build_agent(EveryTurn()), cases, [ANSWER_CORRECT, METRIC_CHOICE]
        )
    )
    assert outcomes["revenue_one_day"].scores == {"answer_correct": 0.0, "metric_choice": 0.0}
    assert outcomes["amsterdam_temperature"].scores["answer_correct"] == 0.0
