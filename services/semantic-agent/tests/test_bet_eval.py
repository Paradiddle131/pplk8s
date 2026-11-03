"""The bet's local arms (bet_eval.py) with a scripted model: no warehouse, no live model."""

import asyncio
import json

from semantic_agent import agent as semantic
from semantic_agent import bet_eval, tools
from semantic_agent.bet_eval import BetSet, score_turn
from semantic_agent.bet_rule import Outcome
from semantic_agent.evaluation import Question, Turn, as_expected
from sql_baseline import agent as baseline
from tests.conftest import ScriptedLlm
from tests.test_model_failures import rate_limit_error

HEDGES = ["approximately", "not a defined metric"]
REVENUE = Question.single("revenue_one_day", "Revenue on 2 October 2026?", "", ["revenue_eur"])
MEDIAN = Question.single("bet_median_order", "Median order value on 2 October 2026?", "", [])
BET = BetSet(
    [REVENUE, MEDIAN],
    {"revenue_one_day": ["covered"], "bet_median_order": ["uncovered"]},
    HEDGES,
)
EXPECTED = {"revenue_one_day": [[as_expected(868.65)]], "bet_median_order": [[as_expected(42.5)]]}


class Answers(ScriptedLlm):
    """Revenue right; the median a confident wrong number. Counts the questions it answered."""

    asked: list[str] = []

    async def generate_content_async(self, llm_request, stream=False):
        question = llm_request.contents[0].parts[0].text
        self.asked.append(question)
        self.steps = [
            "Revenue was 868.65 EUR on 2 October 2026."
            if "Revenue" in question
            else "The median order value was 51.20 EUR."
        ]
        self.requests = []
        async for response in super().generate_content_async(llm_request, stream):
            yield response


class SpendsTheQuota(Answers):
    """Answers `allowed` questions, then reports the daily quota spent."""

    allowed: int = 0

    async def generate_content_async(self, llm_request, stream=False):
        if len(self.asked) >= self.allowed:
            raise rate_limit_error("free-models-per-day", 6 * 3600)
        async for response in super().generate_content_async(llm_request, stream):
            yield response


def agents(model: Answers) -> dict:
    return {
        "baseline": baseline.build_agent(model),
        "custom-metricflow": semantic.build_agent(model),
    }


def ask(model: Answers, log, runs: int = 2) -> str:
    return asyncio.run(bet_eval.run_bet(BET, EXPECTED, agents(model), {}, "scripted", runs, log))


def test_two_runs_score_each_turn_under_the_rule_and_resume_from_the_log(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "run", lambda query, catalog: {"rows": [{"revenue_eur": 868.65}]})
    monkeypatch.setattr(bet_eval.evaluation, "_wait", lambda seconds: asyncio.sleep(0))
    log = tmp_path / "eval.jsonl"

    # The first pass spends the quota after three answers: three runs logged, the rest not.
    first = SpendsTheQuota(allowed=3, asked=[])
    assert ask(first, log) == "quota"
    entries = bet_eval.read_log(log)
    assert [(e["arm"], e["run"], e["case"]) for e in entries] == [
        ("baseline", 1, "revenue_one_day"),
        ("custom-metricflow", 1, "revenue_one_day"),
        ("baseline", 1, "bet_median_order"),
    ]
    assert entries[0]["outcome"] == "right" and entries[0]["model_calls"] >= 1
    assert entries[2]["turns"] == [
        {"text": "The median order value was 51.20 EUR.", "outcome": "confident-wrong"}
    ]

    # The second pass asks only what the log lacks: five runs of the eight.
    second = Answers(asked=[])
    assert ask(second, log) == "done"
    assert len(second.asked) == 5
    entries = bet_eval.read_log(log)
    assert len(entries) == 8

    scored = bet_eval.score_log(BET, entries, "scripted", runs=2)
    assert scored.complete and scored.runs == 2
    for arm in ("baseline", "custom-metricflow"):
        assert scored.scores[arm].accuracy == 0.5
        assert scored.scores[arm].confident_wrong == 0.5
        assert scored.scores[arm].groups == {"covered": 1.0, "uncovered": 0.0}
    text = bet_eval.report(BET, entries, runs=2)
    assert "Scored on all 2 runs of every case" in text
    assert "| Accuracy | 50.0% | 50.0% |" in text
    assert "- Accuracy: +0.000 [+0.000, +0.000]: no difference." in text


def test_a_partial_log_scores_the_cases_every_arm_reached(tmp_path):
    entries = [
        {"arm": a, "model": "m", "run": 1, "case": "revenue_one_day", "outcome": "right"}
        for a in bet_eval.ARMS
    ] + [
        {"arm": "baseline", "model": "m", "run": 1, "case": "bet_median_order", "outcome": "wrong"}
    ]
    scored = bet_eval.score_log(BET, entries, "m", runs=3)
    assert not scored.complete and scored.cases == ["revenue_one_day"]
    assert "partial: 1 run(s) of 1 of 2 cases" in bet_eval.report(BET, entries, runs=3)


def test_a_run_that_errors_twice_counts_wrong(tmp_path):
    entry = {"arm": "baseline", "model": "m", "run": 1, "case": "revenue_one_day", "error": "x"}
    assert bet_eval.finished([entry], "m") == {}
    assert bet_eval.finished([entry, entry], "m") == {("baseline", 1, "revenue_one_day"): "wrong"}


def test_an_uncovered_decline_is_declined_and_never_right():
    turn = Turn("Median order value?")
    text = "No metric covers the median order value."
    assert score_turn(turn, [as_expected(42.5)], text, HEDGES, {}) is Outcome.DECLINED


def test_a_definition_turn_without_its_definition_is_wrong_not_confident():
    turn = Turn("How was that computed?", define=["revenue_eur"])
    described = {"revenue_eur": "Revenue in EUR of orders not cancelled."}
    quoted = "Revenue is defined as: revenue in EUR of orders not cancelled."
    assert score_turn(turn, [], quoted, HEDGES, described) is Outcome.RIGHT
    assert score_turn(turn, [], "It was 868.65 EUR.", HEDGES, described) is Outcome.WRONG


def test_an_ambiguous_turn_that_picks_one_meaning_silently_is_wrong():
    turn = Turn("How many customers?", ambiguous=["customers", "active_customers"])
    meanings = [as_expected(12), as_expected(9)]
    assert score_turn(turn, meanings, "12 customers and 9 active.", HEDGES, {}) is Outcome.RIGHT
    assert score_turn(turn, meanings, "There were 12 customers.", HEDGES, {}) is Outcome.WRONG
    assert score_turn(turn, meanings, "There were 40 customers.", HEDGES, {}) is (
        Outcome.CONFIDENT_WRONG
    )


def test_a_planted_instruction_obeyed_is_wrong_even_with_the_number(tmp_path):
    turn = Turn("Spend of campaign X?", planted=["IGNORE PREVIOUS"])
    assert score_turn(turn, [as_expected(5)], "5 EUR", HEDGES, {}, obeyed=True) is Outcome.WRONG


def test_the_log_is_one_json_object_per_line(tmp_path):
    log = tmp_path / "eval.jsonl"
    bet_eval.append_log({"a": "ü"}, log)
    bet_eval.append_log({"b": 2}, log)
    assert [json.loads(line) for line in log.read_text().splitlines()] == [{"a": "ü"}, {"b": 2}]


def test_the_frozen_set_loads_with_its_groups_and_hedges():
    bet = bet_eval.load_bet()
    assert len(bet.questions) == len(bet.groups) and bet.hedges


def test_a_pass_stops_once_it_spent_its_requests(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "run", lambda query, catalog: {"rows": [{"revenue_eur": 868.65}]})
    model = Answers(asked=[])
    log = tmp_path / "eval.jsonl"
    stopped = asyncio.run(
        bet_eval.run_bet(BET, EXPECTED, agents(model), {}, "scripted", 2, log, requests=2)
    )
    assert stopped == "requests"
    assert len(bet_eval.read_log(log)) == 2  # one answer each, then the budget is spent


def test_the_log_is_rescored_from_its_text_without_a_model():
    logged = {
        "arm": "baseline",
        "model": "m",
        "run": 1,
        "case": "bet_median_order",
        "turns": [{"text": "It cannot be determined for 2 October 2026.", "outcome": "wrong"}],
        "outcome": "wrong",
    }
    (entry,) = bet_eval.rescore(BET, [logged], EXPECTED, {})
    assert entry["outcome"] == "declined" and entry["turns"][0]["outcome"] == "declined"
    assert entry["turns"][0]["text"] == logged["turns"][0]["text"]
