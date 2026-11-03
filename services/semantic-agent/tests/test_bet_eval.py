"""The bet's local arms (bet_eval.py) with a scripted model: no warehouse, no live model."""

import asyncio
import json

import pytest

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


def _rows(arm: str, outcomes: dict[str, list[str]]) -> list[dict]:
    return [
        {"arm": arm, "model": "m", "run": r, "case": c, "outcome": o}
        for c, runs in outcomes.items()
        for r, o in enumerate(runs, 1)
    ]


def test_every_arm_is_read_from_its_own_log_and_named_by_the_file(tmp_path):
    local = _rows("baseline", {"revenue_one_day": ["right"]})
    (tmp_path / "eval-local.jsonl").write_text("".join(json.dumps(e) + "\n" for e in local))
    live = [{"model": "m", "run": 1, "case": "revenue_one_day", "outcome": "right"}]
    (tmp_path / "eval-native-mcp.jsonl").write_text(json.dumps(live[0]) + "\n")
    entries = bet_eval.read_logs(tmp_path)
    assert [e["arm"] for e in entries] == ["baseline", "native-mcp"]
    assert bet_eval.arms_of(entries, "m") == ["baseline", "native-mcp"]


def test_a_third_arm_is_scored_beside_the_local_pair_on_the_cases_all_reached():
    both = {"revenue_one_day": ["right"], "bet_median_order": ["confident-wrong"]}
    entries = (
        _rows("baseline", both)
        + _rows("custom-metricflow", both)
        + _rows("native-mcp", {"revenue_one_day": ["right"]})
    )
    scored = bet_eval.score_log(BET, entries, "m", runs=3)
    assert list(scored.scores) == ["baseline", "custom-metricflow", "native-mcp"]
    assert scored.cases == ["revenue_one_day"] and not scored.complete
    text = bet_eval.report(BET, entries, runs=3, every_arm=True)
    assert text.startswith("# Every arm on the frozen set")
    assert "| Accuracy | 100.0% | 100.0% | 100.0% |" in text


def test_an_arm_of_ours_is_judged_against_the_managed_best_under_the_rule():
    def both(revenue: str, median: str) -> dict[str, list[str]]:
        return {"revenue_one_day": [revenue] * 3, "bet_median_order": [median] * 3}

    entries = (
        _rows("native-context", both("wrong", "right"))
        + _rows("native-shaped", both("right", "wrong"))
        + _rows("native-mcp", both("right", "right"))
        + _rows(
            "custom-toolbox",
            {"revenue_one_day": ["right"] * 3, "bet_median_order": ["confident-wrong"] * 3},
        )
    )
    text = bet_eval.report(BET, entries, runs=3, every_arm=True)
    # A tie on accuracy goes to the lower rung.
    assert "The managed best (RULE.md § The rule, 1): `native-context` on `m`, accuracy 50.0%." in (
        text
    )
    assert "- `native-mcp` (rung 3) on `m` against `native-context` on `m`" in text
    assert "accuracy +0.500" in text
    # Two cases cannot exclude zero: neither arm of ours is worth building on this.
    assert text.count(": not worth building (the check;") == 2


def test_no_managed_arm_means_no_rule_comparison():
    both = {"revenue_one_day": ["right"], "bet_median_order": ["right"]}
    entries = _rows("baseline", both) + _rows("native-mcp", both)
    assert "managed best" not in bet_eval.report(BET, entries, runs=1, every_arm=True)


def test_a_managed_arm_alone_on_its_model_says_there_is_nothing_to_compare():
    both = {"revenue_one_day": ["right"], "bet_median_order": ["declined"]}
    text = bet_eval.report(BET, _rows("native-kc", both), runs=1, every_arm=True)
    assert "The managed best (RULE.md § The rule, 1): `native-kc` on `m`, accuracy 50.0%." in text
    assert "No arm of ours (rung 3 or 4) is logged on any model" in text
    assert "paired by case against it" not in text and not text.endswith("\n\n")


def _unclear(arm: str, case: str, text: str, run: int = 1) -> dict:
    turn = {"text": text, "outcome": "unclear"}
    return {
        "arm": arm,
        "model": "m",
        "run": run,
        "case": case,
        "turns": [turn],
        "outcome": "unclear",
    }


class StubJudge:
    """Gives scripted verdicts in turn, by the answer it is shown; counts what it was asked."""

    def __init__(self, verdicts: dict[str, list[str]]):
        self.verdicts = {k: list(v) for k, v in verdicts.items()}
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        answer = next(a for a in self.verdicts if a in prompt)
        return f"Reasoning.\nVERDICT: {self.verdicts[answer].pop(0)}"


def test_the_judge_decides_unclear_turns_twice_and_a_rescore_spends_nothing(tmp_path):
    declined = "The data covers orders and returns, but there are no page views."
    murky = "Revenue was strong, led by Germany."
    entries = [
        _unclear("native-shaped", "bet_median_order", declined),
        _unclear("native-shaped", "revenue_one_day", murky),
        {"arm": "native-shaped", "model": "m", "run": 1, "case": "x", "outcome": "right"},
    ]
    cache = tmp_path / "judge.jsonl"
    judge = StubJudge({declined: ["declined", "declined"], murky: ["wrong", "right"]})
    why, spent = asyncio.run(bet_eval.judge_turns(BET, entries, EXPECTED, judge, "j:free", cache))
    assert (why, spent) == ("done", 4)
    # Blind: the prompt holds the question, the expected number and the answer, never the arm.
    assert "Median order value on 2 October 2026?" in judge.prompts[0]
    assert "42.5" in judge.prompts[0] and "native-shaped" not in judge.prompts[0]

    judged = bet_eval.apply_verdicts(entries, bet_eval.read_verdicts(cache, "j:free"))
    assert judged[0]["outcome"] == "declined"
    assert judged[0]["turns"][0]["judged"] == ["declined", "declined"]
    assert judged[1]["outcome"] == "unclear"  # two different verdicts: unclear, counted wrong
    assert judged[2] == entries[2]

    # The cache holds every verdict: a second pass asks nothing, and another judge model's
    # verdicts are not this one's.
    again = StubJudge({})
    assert asyncio.run(bet_eval.judge_turns(BET, entries, EXPECTED, again, "j:free", cache)) == (
        "done",
        0,
    )
    assert bet_eval.read_verdicts(cache, "other:free") == {}

    # A changed answer is judged again: the cache is keyed on its hash.
    changed = [_unclear("native-shaped", "bet_median_order", declined + " Sorry.")]
    assert bet_eval.apply_verdicts(changed, bet_eval.read_verdicts(cache))[0]["outcome"] == (
        "unclear"
    )

    text = bet_eval.report(BET, bet_eval.apply_verdicts(entries, bet_eval.read_verdicts(cache)))
    assert "Turns judged: 2; verdicts that stood: 1." in text
    assert "- `native-shaped` `revenue_one_day` run 1 turn 1: wrong / right" in text
    assert "`bet_median_order` run 1" not in text


def test_the_judge_keeps_to_its_request_budget_and_resumes(tmp_path):
    entries = [_unclear("native-kc", "bet_median_order", "Nothing on medians here.")]
    cache = tmp_path / "judge.jsonl"
    judge = StubJudge({"Nothing on medians": ["declined", "declined"]})
    assert asyncio.run(
        bet_eval.judge_turns(BET, entries, EXPECTED, judge, "j:free", cache, requests=1)
    ) == ("requests", 1)
    assert bet_eval.apply_verdicts(entries, bet_eval.read_verdicts(cache))[0]["outcome"] == (
        "unclear"
    )
    asyncio.run(bet_eval.judge_turns(BET, entries, EXPECTED, judge, "j:free", cache))
    assert len(judge.prompts) == 2
    assert bet_eval.apply_verdicts(entries, bet_eval.read_verdicts(cache))[0]["outcome"] == (
        "declined"
    )


def test_a_spent_quota_stops_the_judge(tmp_path):
    entries = [_unclear("native-kc", "bet_median_order", "Nothing on medians here.")]

    async def spent(prompt: str) -> str:
        raise rate_limit_error("free-models-per-day", 3600)

    cache = tmp_path / "judge.jsonl"
    assert asyncio.run(bet_eval.judge_turns(BET, entries, EXPECTED, spent, "j:free", cache)) == (
        "quota",
        1,
    )
    assert not cache.exists()


def test_an_unjudged_turn_is_listed_as_not_judged_yet():
    entries = [_unclear("native-kc", "bet_median_order", "Nothing on medians here.")]
    text = bet_eval.report(BET, entries, runs=1, every_arm=True)
    assert "- `native-kc` `bet_median_order` run 1 turn 1: not judged yet" in text


def test_the_judge_is_a_free_openrouter_model_from_the_factory(monkeypatch):
    from semantic_agent import model

    monkeypatch.setenv("MODEL_BACKEND", "gemini")  # the arms' backend never moves the judge
    assert model.judge_model_id().endswith(":free")
    assert model.build_judge().model == f"openrouter/{model.judge_model_id()}"
    monkeypatch.setenv("JUDGE_MODEL_ID", "some/paid-model")
    with pytest.raises(ValueError, match="must be free"):
        model.build_judge()


def _on(model: str, arm: str, outcomes: dict[str, list[str]]) -> list[dict]:
    return [{**e, "model": model} for e in _rows(arm, outcomes)]


def test_a_managed_arm_on_its_model_is_paired_with_ours_on_another(monkeypatch):
    cases = [f"c{i}" for i in range(12)]
    bet = BetSet([Question.single(c, f"Question {c}?", "", []) for c in cases], {}, HEDGES)
    bet.groups.update({c: ["covered"] for c in cases})
    google, free, claude = "google-data-agent (MODEL_UNSPECIFIED)", "free:free", "claude-x"
    monkeypatch.setattr("semantic_agent.model.DEFAULT_MODEL_ID", free)
    entries = (
        # The managed arms: native-kc beats native-shaped, both on Google's model only.
        _on(google, "native-kc", {c: ["wrong"] * 3 for c in cases})
        + _on(google, "native-shaped", {c: ["wrong"] * 3 for c in cases[:6]})
        + _on(google, "native-shaped", {c: ["right"] * 3 for c in cases[6:]})
        # Ours on the free model: right everywhere, but only run 1 of 10 cases so far.
        + _on(free, "custom-metricflow", {c: ["right"] for c in cases[:10]})
        + _on(free, "baseline", {c: ["right"] for c in cases[:10]})
        # Ours on Claude: no better than the managed best.
        + _on(claude, "custom-metricflow", {c: ["wrong"] * 3 for c in cases[:6]})
        + _on(claude, "custom-metricflow", {c: ["right"] * 3 for c in cases[6:]})
    )
    lines = bet_eval.managed_comparison(bet, entries, runs=3)
    text = "\n".join(lines)
    assert f"`native-shaped` on `{google}`, accuracy 50.0%" in text
    decides = next(line for line in lines if f"`custom-metricflow` (rung 4) on `{free}`" in line)
    assert f"against `native-shaped` on `{google}`, 10 of 12 cases" in decides
    assert (
        "accuracy +0.600" in decides and ": worth building (decides; 10 runs finished)" in decides
    )
    check = next(line for line in lines if f"on `{claude}`" in line)
    assert "accuracy +0.000" in check and ": not worth building (the check;" in check
    assert "the verdict moves with the model" in text
    # The baseline is the reference, on no rung: it is never compared under the rule.
    assert "`baseline` (" not in text
    # eval.md shows the pair in its own section after the models'.
    report = bet_eval.report(bet, entries, runs=3, every_arm=True)
    assert report.index("## The rule across models") > report.index(f"## `{claude}`")
