"""The bet's local arms (bet_eval.py) with a scripted model: no warehouse, no live model."""

import asyncio
import json
from pathlib import Path

import pytest

from semantic_agent import agent as semantic
from semantic_agent import bet_eval, bet_rule, tools
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
    turn = dict(entries[2]["turns"][0])
    # #439: the run's ADK session and the turn's invocation, which the audit rows key on.
    assert entries[2]["session_id"] and turn.pop("invocation_id")
    assert turn == {
        "text": "The median order value was 51.20 EUR.",
        "outcome": "confident-wrong",
        "calls": [],
    }

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


def test_the_bets_baseline_has_the_legacy_tables_in_reach_and_its_runs_say_so(
    monkeypatch, tmp_path
):
    """RULE.md § The arms: legacy beside the trusted layers for every SQL arm (#357); the runs
    logged before it lack the field, so the report tells the two apart."""
    monkeypatch.setattr(tools, "run", lambda query, catalog: {"rows": [{"revenue_eur": 868.65}]})
    model, sql_model = Answers(asked=[]), Answers(asked=[])
    built = {
        "baseline": baseline.build_agent(sql_model, extra_tables=bet_eval.LEGACY_TABLES),
        "custom-metricflow": semantic.build_agent(model),
    }
    log = tmp_path / "eval.jsonl"
    asyncio.run(
        bet_eval.run_bet(BET, EXPECTED, built, {}, "scripted", 1, log, legacy=bet_eval.LEGACY_REACH)
    )
    entries = bet_eval.read_log(log)
    assert {e["arm"]: e.get("legacy", False) for e in entries} == {
        "baseline": True,
        "custom-metricflow": False,
    }
    told = str(sql_model.requests[0].config.system_instruction)
    assert all(table in told for table in bet_eval.LEGACY_TABLES)
    earlier = {**entries[0], "run": 2}
    earlier.pop("legacy")
    text = bet_eval.report(BET, [*entries, earlier], runs=1)
    assert "2 of `baseline`'s 3 logged runs had the `legacy` tables in reach" in text


def test_the_equal_reach_arms_are_configuration_only():
    assert bet_eval.RUNG["native-kc-reach"] == bet_eval.RUNG["native-context-bare"] == 1


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
    # #382: anything but the quote is the blind judge's to read, never confident-wrong.
    assert score_turn(turn, [], "It was 868.65 EUR.", HEDGES, described) is Outcome.UNCLEAR


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
    assert "Turns judged: 2 (2 the code left unclear, 0 confident-wrong with a hedge" in text
    assert "verdicts that stood: 1." in text
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


def test_a_judge_failing_upstream_stops_the_pass_and_says_so(tmp_path, capsys):
    entries = [
        _unclear("native-kc", "bet_median_order", "Nothing on medians here."),
        _unclear("native-kc", "revenue_one_day", "Revenue was strong, led by Germany."),
    ]

    async def down(prompt: str) -> str:
        raise RuntimeError("litellm.APIError: OpenrouterException - upstream request failed")

    cache = tmp_path / "judge.jsonl"
    assert asyncio.run(bet_eval.judge_turns(BET, entries, EXPECTED, down, "j:free", cache)) == (
        "unavailable",
        bet_eval.JUDGE_FAILURES,
    )
    assert "judge unavailable: litellm.APIError" in capsys.readouterr().out
    assert not cache.exists()


def test_one_failed_judge_request_is_skipped_and_the_pass_goes_on(tmp_path):
    text = "Nothing on medians here."
    entries = [_unclear("native-kc", "bet_median_order", text)]
    judge = StubJudge({text: ["declined", "declined"]})
    calls = 0

    async def flaky(prompt: str) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("upstream request failed")
        return await judge(prompt)

    cache = tmp_path / "judge.jsonl"
    assert asyncio.run(bet_eval.judge_turns(BET, entries, EXPECTED, flaky, "j:free", cache)) == (
        "done",
        2,
    )
    assert len(cache.read_text().splitlines()) == 1  # the failed verdict is asked on a later pass


def test_an_unjudged_turn_is_listed_as_not_judged_yet():
    entries = [_unclear("native-kc", "bet_median_order", "Nothing on medians here.")]
    text = bet_eval.report(BET, entries, runs=1, every_arm=True)
    assert "- `native-kc` `bet_median_order` run 1 turn 1: not judged yet" in text


RISE = Question.single(
    "hard_cost_per_booking_rise", "How much did the cost per booking rise in October?", "", []
)
RISE_BET = BetSet([RISE], {"hard_cost_per_booking_rise": ["composable"]}, HEDGES)


def test_the_judge_selects_the_turns_the_report_leaves_unclear(tmp_path):
    """#426: a small expected number that is not the answer's own first figure is unclear under
    the full rescore (#382); the judge's selection reads the same scoring as the report, so it
    asks about that turn instead of leaving it to count as wrong."""
    answer = "It rose from 98.00 EUR to 125.00 EUR, an increase of 27.00 EUR."
    row = {"arm": "baseline", "model": "m", "run": 1, "case": RISE.id, "outcome": "right"}
    row["turns"] = [{"text": answer, "outcome": "right"}]  # as logged before #382
    (tmp_path / "eval-local.jsonl").write_text(json.dumps(row) + "\n")
    (tmp_path / "expected.json").write_text(
        json.dumps({"sets": {"frozen": {RISE.id: [[as_expected(27.0)]]}}})
    )

    # Without the expected numbers the log's "right" stands and nothing would be judged.
    assert bet_eval.undecided_turns(bet_eval.recode(RISE_BET, [row]), HEDGES) == []

    scored = bet_eval.scored_logs(RISE_BET, tmp_path)
    assert scored[0]["turns"][0]["outcome"] == "unclear"
    cache = tmp_path / "judge.jsonl"
    waiting = bet_eval.pending_verdicts(RISE_BET, scored, "j", cache)
    assert waiting == [(("baseline", "m", RISE.id, 1, 0), answer)]
    # judged_logs reads that same scoring: the report's unclear turn is the judge's pending one.
    assert bet_eval.judged_logs(RISE_BET, tmp_path)[0]["outcome"] == "unclear"

    judge = StubJudge({answer: ["right", "right"]})
    expected = bet_eval.read_expected("frozen", tmp_path)
    asyncio.run(bet_eval.judge_turns(RISE_BET, scored, expected, judge, "j", cache))
    assert "27" in judge.prompts[0]
    assert bet_eval.pending_verdicts(RISE_BET, scored, "j", cache) == []
    judged = bet_eval.apply_verdicts(scored, bet_eval.read_verdicts(cache, "j"))
    assert judged[0]["outcome"] == "right"


def _stub_claude(tmp_path: Path, payload: dict, code: int = 0) -> list[str]:
    """A stand-in `claude` that records its arguments and stdin, then prints `payload`."""
    script = tmp_path / "claude_stub.py"
    script.write_text(
        "import json, sys, pathlib\n"
        f"pathlib.Path({str(tmp_path / 'args.json')!r}).write_text(json.dumps("
        "{'argv': sys.argv[1:], 'stdin': sys.stdin.read(), "
        "'system': pathlib.Path(sys.argv[sys.argv.index('--system-prompt-file') + 1]).read_text()"
        "}))\n"
        f"print(json.dumps({payload!r}))\n"
        f"sys.exit({code})\n"
    )
    import sys

    return [sys.executable, str(script)]


def test_the_claude_judge_is_one_tool_less_claude_p_process_a_verdict(tmp_path):
    """#427: the judge prompt is the system prompt of a fresh `claude -p` with no tool, no MCP
    server, no settings and no saved session; its reply is the JSON's `result`."""
    command = _stub_claude(tmp_path, {"result": "Fine.\nVERDICT: right", "is_error": False})
    judge = bet_eval.claude_judge("haiku", command)
    reply = asyncio.run(judge(bet_rule.judge_prompt("Revenue?", [[868.65]], "868.65 EUR")))
    assert bet_rule.parse_verdict(reply) is Outcome.RIGHT
    seen = json.loads((tmp_path / "args.json").read_text())
    argv = seen["argv"]
    assert argv[:3] == ["-p", "--model", "haiku"]
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert "--strict-mcp-config" in argv and "--no-session-persistence" in argv
    assert "868.65 EUR" in seen["system"] and "VERDICT" in seen["stdin"]


def test_a_spent_subscription_limit_stops_the_claude_judge_and_scores_nothing(tmp_path):
    command = _stub_claude(
        tmp_path, {"result": "Claude AI usage limit reached|1762700000", "is_error": True}, code=1
    )
    entries = [_unclear("native-kc", "bet_median_order", "Nothing on medians here.")]
    cache = tmp_path / "judge.jsonl"
    judge = bet_eval.claude_judge("haiku", command)
    why, spent = asyncio.run(
        bet_eval.judge_turns(BET, entries, EXPECTED, judge, "claude -p (haiku)", cache)
    )
    assert (why, spent) == ("limit", 1)
    assert not cache.exists()  # no verdict written, so no turn is scored by it


def test_a_failed_claude_process_is_a_failed_request(tmp_path):
    command = _stub_claude(tmp_path, {"result": "boom", "is_error": True}, code=1)
    with pytest.raises(RuntimeError, match="claude -p failed"):
        asyncio.run(bet_eval.claude_judge("haiku", command)("prompt"))


def test_the_judge_asks_several_verdicts_at_once_and_writes_each(tmp_path):
    entries = [
        _unclear("native-kc", "bet_median_order", f"Nothing on medians here, try {n}.", run=n)
        for n in (1, 2, 3)
    ]
    judge = StubJudge({f"try {n}": ["declined", "declined"] for n in (1, 2, 3)})
    cache = tmp_path / "judge.jsonl"
    why, spent = asyncio.run(
        bet_eval.judge_turns(BET, entries, EXPECTED, judge, "j", cache, concurrency=4)
    )
    assert (why, spent) == ("done", 6)
    judged = bet_eval.apply_verdicts(entries, bet_eval.read_verdicts(cache, "j"))
    assert [e["outcome"] for e in judged] == ["declined"] * 3


def test_the_judge_backend_switch(monkeypatch):
    from semantic_agent import model

    monkeypatch.delenv("BET_JUDGE_BACKEND", raising=False)
    assert model.judge_backend() == "claude"
    assert model.judge_model_id() == "claude -p (haiku)"
    monkeypatch.setenv("BET_JUDGE_BACKEND", "openrouter")
    assert model.judge_model_id().endswith(":free")
    monkeypatch.setenv("BET_JUDGE_BACKEND", "gemini")
    with pytest.raises(ValueError, match="BET_JUDGE_BACKEND"):
        model.judge_backend()


def test_the_judge_is_a_free_openrouter_model_from_the_factory(monkeypatch):
    from semantic_agent import model

    monkeypatch.setenv("BET_JUDGE_BACKEND", "openrouter")
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


def _turn(arm: str, case: str, text: str, outcome: str, run: int = 1) -> dict:
    turn = {"text": text, "outcome": outcome}
    return {"arm": arm, "model": "m", "run": run, "case": case, "turns": [turn], "outcome": outcome}


def test_a_confident_wrong_turn_hedged_outside_the_list_goes_to_the_judge(tmp_path):
    hedged = "Based on first orders as the signup date, 0 customers signed up."
    kept = "The median order value was 51.20 EUR, based on 15 orders."
    plain = "The median order value was 51.20 EUR."
    entries = [
        _turn("baseline", "revenue_one_day", hedged, "confident-wrong"),
        _turn("baseline", "bet_median_order", kept, "confident-wrong"),
        _turn("baseline", "bet_median_order", plain, "confident-wrong", run=2),
    ]
    # Only the turns with a hedge-like phrase outside the list are the judge's; "approximately" is
    # on the list, so a turn holding only it is never confident-wrong to begin with.
    assert [k[3] for k, _ in bet_eval.undecided_turns(entries, HEDGES)] == [1, 1]
    assert bet_rule.unlisted_hedges("Approximately 5.", HEDGES) == []
    waiting = bet_eval.report(BET, entries, runs=2, every_arm=True)
    assert "Confident-wrong turns with a hedge outside the list, awaiting the judge:" in waiting

    cache = tmp_path / "judge.jsonl"
    judge = StubJudge({hedged: ["wrong", "wrong"], kept: ["confident-wrong", "confident-wrong"]})
    assert asyncio.run(bet_eval.judge_turns(BET, entries, EXPECTED, judge, "j:free", cache)) == (
        "done",
        4,
    )
    judged = bet_eval.apply_verdicts(entries, bet_eval.read_verdicts(cache))
    assert [e["outcome"] for e in judged] == ["wrong", "confident-wrong", "confident-wrong"]
    assert judged[0]["turns"][0]["coded"] == "confident-wrong"
    text = bet_eval.report(BET, judged, runs=2, every_arm=True)
    assert "Confident-wrong turns the judge moved: 1 of 2 (1 to wrong, hedged; 0 to unclear)." in (
        text
    )
    assert "awaiting the judge" not in text


@pytest.mark.parametrize(
    ("verdicts", "outcome"),
    [
        (["wrong", "wrong"], "wrong"),
        (["confident-wrong", "confident-wrong"], "confident-wrong"),
        (["declined", "declined"], "wrong"),  # a decline beside the number is a hedge
        (["right", "right"], "unclear"),  # the parsed number is outside tolerance
        (["wrong", "confident-wrong"], "unclear"),
    ],
)
def test_two_verdicts_on_a_hedged_number(tmp_path, verdicts, outcome):
    text = "It may be 51.20 EUR."
    entries = [_turn("baseline", "bet_median_order", text, "confident-wrong")]
    cache = tmp_path / "judge.jsonl"
    asyncio.run(
        bet_eval.judge_turns(BET, entries, EXPECTED, StubJudge({text: verdicts}), "j", cache)
    )
    assert bet_eval.apply_verdicts(entries, bet_eval.read_verdicts(cache))[0]["outcome"] == outcome


def _write(path, rows) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in rows))


def test_each_set_reads_only_its_own_logs_and_names_its_arms_by_the_file(tmp_path):
    _write(tmp_path / "eval-local.jsonl", _rows("baseline", {"revenue_one_day": ["right"]}))
    live = {"model": "m", "run": 1, "case": "revenue_one_day", "outcome": "right"}
    _write(tmp_path / "eval-native-kc.jsonl", [live])
    _write(tmp_path / "eval-hard-local.jsonl", _rows("baseline", {"hard_aov": ["wrong"]}))
    _write(tmp_path / "eval-hard-native-kc.jsonl", [{**live, "case": "hard_aov"}])

    frozen = bet_eval.read_logs(tmp_path)
    assert [(e["arm"], e["case"]) for e in frozen] == [
        ("baseline", "revenue_one_day"),
        ("native-kc", "revenue_one_day"),
    ]
    hard = bet_eval.read_logs(tmp_path, "hard")
    assert [(e["arm"], e["case"]) for e in hard] == [
        ("baseline", "hard_aov"),
        ("native-kc", "hard_aov"),
    ]
    files = bet_eval.SETS["hard"]
    assert files.local_log(tmp_path).name == "eval-hard-local.jsonl"
    assert files.local_report(tmp_path).name == "eval-hard-local.md"
    assert files.arm_log("native-kc", tmp_path).name == "eval-hard-native-kc.jsonl"


def test_the_hard_set_loads_by_name_with_its_groups():
    hard = bet_eval.load_set("hard")
    assert hard.name == "hard" and len(hard.questions) >= 40
    assert all(q.id.startswith("hard_") for q in hard.questions)
    assert set(hard.groups) == {q.id for q in hard.questions}
    whole = bet_eval.load_set(overlay=Path("/nonexistent"))
    assert whole.name == "frozen" and len(whole.questions) == 96


def test_the_judge_cache_keeps_each_sets_verdicts_apart(tmp_path):
    murky = "Revenue was strong, led by Germany."
    entries = [_unclear("native-kc", "revenue_one_day", murky)]
    cache = tmp_path / "judge.jsonl"
    hard = BetSet(BET.questions, BET.groups, BET.hedges, "hard")
    judge = StubJudge({murky: ["wrong", "wrong"]})
    assert asyncio.run(bet_eval.judge_turns(hard, entries, EXPECTED, judge, "j", cache)) == (
        "done",
        2,
    )
    assert {r["set"] for r in bet_eval.read_log(cache)} == {"hard"}
    # The hard set's verdicts are never the frozen set's, even on the same turn key.
    assert bet_eval.read_verdicts(cache, "j") == {}
    assert bet_eval.apply_verdicts(entries, bet_eval.read_verdicts(cache, "j", "hard"))[0][
        "outcome"
    ] == ("wrong")
    # The frozen set's pass asks its own, and a row naming no set (before #364) is the frozen set's.
    frozen = StubJudge({murky: ["right", "right"]})
    assert asyncio.run(bet_eval.judge_turns(BET, entries, EXPECTED, frozen, "j", cache))[1] == 2
    rows = [r for r in bet_eval.read_log(cache) if r["set"] == "frozen"]
    _write(cache, [{k: v for k, v in r.items() if k != "set"} for r in rows])
    assert bet_eval.apply_verdicts(entries, bet_eval.read_verdicts(cache, "j"))[0]["outcome"] == (
        "right"
    )
    assert bet_eval.read_verdicts(cache, "j", "hard") == {}


def test_eval_md_scores_each_set_in_its_own_section(monkeypatch, tmp_path):
    monkeypatch.setattr("semantic_agent.model.judge_model_id", lambda: "j")
    frozen = bet_eval.load_set().questions[0].id
    hard = bet_eval.load_set("hard").questions[0].id
    _write(tmp_path / "eval-native-kc.jsonl", _rows("native-kc", {frozen: ["right"]}))
    _write(tmp_path / "eval-hard-native-kc.jsonl", _rows("native-kc", {hard: ["declined"]}))
    path = bet_eval.write_every_arm(tmp_path, runs=1)
    assert path == tmp_path / "eval.md"
    text = path.read_text()
    assert text.startswith("# Every arm on the bet's sets\n")
    before, after = text.split("\n## Every arm on the hard set\n")
    assert "\n## Every arm on the frozen set\n" in before
    assert "96 cases of `services/semantic-agent/evals/semantic_bet.yaml`" in before
    assert "accuracy 100.0%" in before and "### The rule across models" in before
    assert "cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`" in after
    assert "[`eval-hard-local.jsonl`](eval-hard-local.jsonl)" in after
    assert "accuracy 0.0%" in after and "### The rule across models" in after


DEFINE = Question("bet_define", [Turn("How was revenue computed?", define=["revenue_eur"])])
PLANTED = Question("bet_planted", [Turn("Spend of campaign X?", planted=["IGNORE PREVIOUS"])])
RECODE = BetSet(
    [REVENUE, MEDIAN, DEFINE, PLANTED],
    {**BET.groups, "bet_define": ["conversation"], "bet_planted": ["planted"]},
    HEDGES,
)
# Logged under the wordings before #367: a decline the code then missed, beside a number and alone.
NOT_TRACKED = "The median is not tracked in the governed tables; daily leads ranged from 3 to 4."
NOT_TRACKED_ALONE = "Order medians are not tracked in the database."


def test_a_live_arms_log_is_scored_on_read_under_the_new_wordings_and_never_rewritten(tmp_path):
    rows = [
        _turn("native-governed", "bet_median_order", NOT_TRACKED, "confident-wrong"),
        _turn("native-governed", "bet_median_order", NOT_TRACKED_ALONE, "unclear", run=2),
        _turn("native-governed", "revenue_one_day", "Revenue was 868.65 EUR.", "right"),
    ]
    log = tmp_path / "eval-native-governed.jsonl"
    log.write_text("".join(json.dumps(e) + "\n" for e in rows))
    before = log.read_text()
    judged = bet_eval.judged_logs(RECODE, tmp_path)
    assert [e["outcome"] for e in judged] == ["wrong", "declined", "right"]
    assert judged[0]["turns"][0]["logged"] == "confident-wrong"
    assert judged[1]["turns"][0]["logged"] == "unclear"
    assert "logged" not in judged[2]["turns"][0]
    assert log.read_text() == before
    # Neither is the judge's any more: the code decides both.
    assert bet_eval.undecided_turns(judged, HEDGES) == []
    text = bet_eval.report(RECODE, judged, runs=2, every_arm=True)
    assert (
        "Turns the current wordings score otherwise than their log (RULE.md § Changes since "
        "freezing, applied on read): 2 (`native-governed` 1 confident-wrong to wrong; "
        "`native-governed` 1 unclear to declined)."
    ) in text


def test_scoring_on_read_agrees_with_a_rescore_from_the_expected_numbers():
    texts = [
        NOT_TRACKED,
        NOT_TRACKED_ALONE,
        "The median order value was 51.20 EUR.",
        "Revenue was strong, led by Germany.",
        "Approximately 51.20 EUR.",
        "",
    ]
    # As the old wordings logged them: the code then took "not tracked" for nothing.
    logged = ["confident-wrong", "unclear", "confident-wrong", "unclear", "wrong", "unclear"]
    entries = [
        _turn("native-kc", "bet_median_order", t, o, run=r)
        for r, (t, o) in enumerate(zip(texts, logged, strict=True), 1)
    ]
    on_read = [t["outcome"] for e in bet_eval.recode(RECODE, entries) for t in e["turns"]]
    rescored = [
        t["outcome"] for e in bet_eval.rescore(RECODE, entries, EXPECTED, {}) for t in e["turns"]
    ]
    assert (
        on_read
        == rescored
        == ["wrong", "declined", "confident-wrong", "unclear", "wrong", "unclear"]
    )


def test_scoring_on_read_keeps_right_planted_and_unknown_turns_and_reads_a_definition_turn():
    entries = [
        _turn("native-kc", "revenue_one_day", "It is not tracked, but 868.65 EUR.", "right"),
        _turn("native-kc", "bet_planted", "Campaign spend is not tracked.", "wrong"),
        _turn("native-kc", "elsewhere", "Not tracked.", "unclear"),
        _turn("native-kc", "bet_define", "How revenue is computed is not tracked here.", "wrong"),
        _turn("native-kc", "bet_define", "It was 868.65 EUR, not tracked otherwise.", "wrong"),
    ]
    assert [e["outcome"] for e in bet_eval.recode(RECODE, entries)] == [
        "right",
        "wrong",
        "unclear",
        "declined",
        "wrong",
    ]


def test_a_scope_caveat_beside_a_wider_figure_goes_to_the_judge():
    caveat = (
        "Net revenue on 1 October 2026 was €956.94. The semantic layer cannot split revenue by "
        "customer country, so this figure covers all countries, not Germany specifically."
    )
    entries = [_turn("custom-lightdash", "revenue_one_day", caveat, "confident-wrong")]
    assert bet_eval.recode(RECODE, entries) == entries
    assert [k[2] for k, _ in bet_eval.undecided_turns(entries, HEDGES)] == ["revenue_one_day"]


def test_both_sets_decide_and_a_disagreement_goes_to_the_cheaper_rung(monkeypatch):
    cases = [f"c{i}" for i in range(12)]
    google, free = "google-data-agent (MODEL_UNSPECIFIED)", "free:free"
    monkeypatch.setattr("semantic_agent.model.DEFAULT_MODEL_ID", free)

    def a_set(name: str) -> BetSet:
        qs = [Question.single(c, f"Question {c}?", "", []) for c in cases]
        return BetSet(qs, {c: ["covered"] for c in cases}, HEDGES, name)

    managed = _on(google, "native-kc", {c: ["wrong"] * 3 for c in cases})
    better = _on(free, "custom-metricflow", {c: ["right"] * 3 for c in cases})
    level = _on(free, "custom-metricflow", {c: ["wrong"] * 3 for c in cases})

    # Ours on the frozen set only: the line says it cannot apply yet.
    frozen_only = {"frozen": (a_set("frozen"), managed + better), "hard": (a_set("hard"), managed)}
    text = "\n".join(bet_eval.both_sets(frozen_only, runs=3))
    assert "## The rule on both sets" in text
    assert "It cannot apply yet: no arm of ours (rung 3 or 4) is logged on the hard set" in text
    assert "undecided until it is paired on both sets" in text

    # Worth on the frozen set, not on the hard one: the cheaper rung wins.
    disagree = {"frozen": frozen_only["frozen"], "hard": (a_set("hard"), managed + level)}
    text = "\n".join(bet_eval.both_sets(disagree, runs=3))
    assert "cannot apply yet" not in text
    assert (
        f"- `custom-metricflow` on `{free}` (decides): the frozen set: worth; the hard set: not "
        "worth; on both sets: not worth building (the sets disagree: the cheaper rung wins)."
    ) in text

    # Worth on both: worth building.
    agree = {"frozen": frozen_only["frozen"], "hard": (a_set("hard"), managed + better)}
    assert "on both sets: worth building." in "\n".join(bet_eval.both_sets(agree, runs=3))


def test_step_three_names_the_cheapest_rung_that_ties_the_best_on_both_sets():
    cases = [f"c{i}" for i in range(12)]
    google, free = "google-data-agent (MODEL_UNSPECIFIED)", "free:free"

    def a_set(name: str) -> BetSet:
        qs = [Question.single(c, f"Question {c}?", "", []) for c in cases]
        return BetSet(qs, {c: ["covered"] for c in cases}, HEDGES, name)

    best = _on(google, "native-governed", {c: ["right"] * 3 for c in cases})
    # Rung 1, level with the rung-2 best on every case: it ties on both sets and is cheaper.
    cheap = _on(google, "native-context", {c: ["right"] * 3 for c in cases})
    # Rung 4, level too: it ties but is on a dearer rung.
    ours = _on(free, "custom-metricflow", {c: ["right"] * 3 for c in cases})
    # Rung 1, right on the frozen set only: it ties there, not on the hard set.
    half = _on(google, "native-kc", {c: ["right"] * 3 for c in cases})
    missed = _on(google, "native-kc", {c: ["wrong"] * 3 for c in cases})
    # Rung 1, right on two cases only (a pass under way): never a tie, however wide its interval.
    started = _on(google, "native-kc-reach", {c: ["right"] * 3 for c in cases[:2]})
    sets = {
        "frozen": (a_set("frozen"), best + cheap + ours + half + started),
        "hard": (a_set("hard"), best + cheap + ours + missed),
    }
    text = "\n".join(bet_eval.step_three(sets, runs=3))
    assert "`native-context` on `google-data-agent (MODEL_UNSPECIFIED)` (rung 1)" in text
    assert "`custom-metricflow` on `free:free` (rung 4)" in text
    assert "`native-kc`" not in text and "`native-kc-reach`" not in text
    assert "The cheapest rung among them is 1: `native-context` on" in text
    assert "Step 3 cannot apply yet: no managed best on the hard set" in "\n".join(
        bet_eval.step_three({"frozen": sets["frozen"], "hard": (a_set("hard"), ours)}, runs=3)
    )


def test_an_arm_still_under_way_is_never_the_managed_best():
    cases = [f"c{i}" for i in range(12)]
    google, early = "google-data-agent (MODEL_UNSPECIFIED)", "google-data-agent (LATEST_GA_MODEL)"
    qs = [Question.single(c, f"Question {c}?", "", []) for c in cases]
    bet = BetSet(qs, {c: ["covered"] for c in cases}, HEDGES, "frozen")
    whole = _on(google, "native-context", {c: ["right", "right", "wrong"] for c in cases})
    started = _on(early, "native-context-bare", {c: ["right"] * 3 for c in cases[:2]})
    managed, _, _ = bet_eval.step_two(bet, whole + started, runs=3)
    assert managed is not None and managed[:2] == ("native-context", google)


def test_a_pass_does_not_start_when_the_audit_database_is_unreachable(monkeypatch):
    monkeypatch.setenv("AUDIT_URL", "postgresql://agent_audit:agent_audit@127.0.0.1:1/none")
    problem = bet_eval.warehouse_unreachable()
    assert problem is not None and problem.startswith("the audit database is unreachable")


def test_results_hold_every_arm_with_its_intervals(tmp_path, monkeypatch):
    cases = [f"c{i}" for i in range(6)]
    qs = [Question.single(c, f"Question {c}?", "", []) for c in cases]
    bet = BetSet(qs, {c: ["covered"] for c in cases}, HEDGES, "frozen")
    entries = _on("g", "native-context", {c: ["right", "right", "wrong"] for c in cases})
    row = bet_eval.arm_result(bet, entries, "native-context", "g", runs=3)
    assert row["runs"] == 18 and row["cases"] == 6 and row["rung"] == 1
    assert abs(row["accuracy"][0] - 2 / 3) < 1e-9 and row["accuracy"][1] <= row["accuracy"][0]
    assert row["groups"]["covered"][1] == 6 and row["pass_all"] == 0
    assert row["outcomes"] == {"right": 12, "wrong": 6}


def test_the_canary_is_the_first_single_turn_covered_case():
    probe = bet_eval.canary_case(BET)
    assert probe is not None and probe.id == "revenue_one_day"
    only_uncovered = BetSet([MEDIAN], {"bet_median_order": ["uncovered"]}, HEDGES, "frozen")
    assert bet_eval.canary_case(only_uncovered) is None


class Withheld(Answers):
    """Every answer is the broken warehouse's: no figure, the audit row unwritten."""

    async def generate_content_async(self, llm_request, stream=False):
        self.asked.append(llm_request.contents[0].parts[0].text)
        self.steps = ["The audit record could not be written, so the result was withheld."]
        self.requests = []
        async for response in ScriptedLlm.generate_content_async(self, llm_request, stream):
            yield response


def test_a_local_pass_stops_at_the_canary_and_logs_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(bet_eval.evaluation, "_wait", lambda seconds: asyncio.sleep(0))
    log = tmp_path / "eval.jsonl"
    broken = Withheld(asked=[])
    why = asyncio.run(
        bet_eval.run_bet(BET, EXPECTED, agents(broken), {}, "scripted", 2, log, canary=True)
    )
    assert why == "canary" and not log.exists()
    assert len(broken.asked) == bet_eval.CANARY_TRIES  # the first arm's two tries, nothing else
    healthy = Answers(asked=[])
    assert (
        asyncio.run(
            bet_eval.run_bet(BET, EXPECTED, agents(healthy), {}, "scripted", 1, log, canary=True)
        )
        == "done"
    )
    assert len(bet_eval.read_log(log)) == 4  # the canaries are never logged


def test_each_row_names_the_harness_that_ran_its_model():
    assert bet_eval.harness("claude-code (haiku)") == "claude-code-subagent"
    assert bet_eval.harness("claude-haiku-5-5") == "adk-anthropic-api"
    assert bet_eval.harness("google-data-agent (LATEST_GA_MODEL)") == "google-data-agent"
    assert bet_eval.harness("nvidia/nemotron-3.5-super-vl:free") == "adk-openrouter"


def test_each_row_says_how_many_questions_shared_a_session():
    assert bet_eval.session_kind("claude-code (haiku)") == "shared per batch"
    assert bet_eval.session_kind("claude-code (fresh-haiku)") == "fresh per case"
    # The Bash-and-Read-only agent type ran one fresh subagent per case too (#374, 2026-11-05).
    assert bet_eval.session_kind("claude-code (subject-haiku)") == "fresh per case"
    assert bet_eval.session_kind("claude-haiku-5-5") == "fresh per run"


def test_a_k1_pass_writes_every_arm_at_the_rules_k(monkeypatch, tmp_path):
    """A pass asked at --runs 1 still scores eval.md and results.json at the rule's k: written at
    the pass's own k, a k = 1 free-model pass cut every other arm's runs 2 and 3 (2026-11-05)."""
    monkeypatch.setattr("semantic_agent.model.judge_model_id", lambda: "j")
    log, report = tmp_path / "eval-local.jsonl", tmp_path / "eval-local.md"
    log.write_text("")
    monkeypatch.setattr(bet_eval.SetFiles, "local_log", lambda self, directory=None: log)
    monkeypatch.setattr(bet_eval.SetFiles, "local_report", lambda self, directory=None: report)
    written = []
    monkeypatch.setattr(bet_eval, "write_every_arm", lambda **kw: written.append(kw) or tmp_path)
    assert asyncio.run(bet_eval.main(["--report-only", "--runs", "1"])) in (0, 3)
    assert written == [{}] and report.exists()


def test_hard_v2_loads_by_name_with_its_new_cases_and_canary_and_does_not_decide():
    v2 = bet_eval.load_set("hard-v2", overlay=Path("/nonexistent"))
    assert v2.name == "hard-v2" and len(v2.questions) == 58 and len(v2.new) == 15
    # As scored, without the cases #382 and #434 retired (the overlay beside the logs).
    scored = bet_eval.load_set("hard-v2")
    assert len(scored.questions) == 54 and "hv2_first_order_value_october" not in scored.new
    assert "hard_active_customers_week" not in {q.id for q in scored.questions}
    assert all(case.startswith("hv2_") for case in v2.new)
    assert bet_eval.canary_case(v2).id == "hard_top_channel_bookings"
    assert bet_eval.SETS["hard-v2"].arm_log("native-kc").name == "eval-hard-v2-native-kc.jsonl"
    # Until the owner's go (#380, #381), the rule's verdict reads the frozen set and v1.
    assert bet_eval.DECIDING == ("frozen", "hard")


def test_each_set_version_reads_only_its_own_logs(tmp_path):
    live = {"model": "m", "run": 1, "outcome": "right"}
    _write(tmp_path / "eval-hard-native-kc.jsonl", [{**live, "case": "hard_aov_last_month"}])
    _write(
        tmp_path / "eval-hard-v2-native-kc.jsonl", [{**live, "case": "hv2_median_customer_spend"}]
    )
    assert [e["case"] for e in bet_eval.read_logs(tmp_path, "hard")] == ["hard_aov_last_month"]
    assert [e["case"] for e in bet_eval.read_logs(tmp_path, "hard-v2")] == [
        "hv2_median_customer_spend"
    ]
    assert bet_eval.read_logs(tmp_path) == []


def test_an_arm_on_a_set_version_reports_its_new_cases_apart():
    v2 = bet_eval.load_set("hard-v2")
    rows = [
        {"arm": "baseline", "model": "m", "run": 1, "case": c, "outcome": "right", "turns": []}
        for c in ("hard_aov_last_month", "hv2_median_customer_spend")
    ]
    rows.append({**rows[1], "case": "hv2_signups_never_ordered", "outcome": "declined"})
    rows[0]["carried_from"] = "hard"
    result = bet_eval.arm_result(v2, rows, "baseline", "m", 1)
    assert result["new"]["all"] == [0.5, 2]
    assert result["new"]["uncovered"] == [1.0, 1] and result["new"]["composable"] == [0.0, 1]
    assert result["carried_runs"] == 1
    assert "new" not in bet_eval.arm_result(bet_eval.load_set("hard"), rows, "baseline", "m", 1)


def _overlay(directory, rows):
    _write(directory / bet_eval.OVERLAY, rows)


def test_a_redacted_run_leaves_every_read_and_a_rerun_of_it_is_kept(tmp_path):
    first = {"model": "m", "run": 1, "case": "revenue_one_day", "outcome": "wrong", "at": "t1"}
    other = {**first, "case": "orders_one_day", "outcome": "right"}
    _write(tmp_path / "eval-native-kc.jsonl", [first, other])
    redact = {"kind": "run", "arm": "native-kc", **{k: first[k] for k in ("model", "case", "run")}}
    _overlay(tmp_path, [{**redact, "at": "t1", "reason": "infrastructure failure"}])
    assert [e["case"] for e in bet_eval.read_logs(tmp_path)] == ["orders_one_day"]
    # The log itself is untouched, and its raw read still has both rows.
    assert len(bet_eval.read_log(tmp_path / "eval-native-kc.jsonl", raw=True)) == 2
    # The runner asks the run again; the rerun has its own `at`, so it is kept.
    with (tmp_path / "eval-native-kc.jsonl").open("a") as log:
        log.write(json.dumps({**first, "outcome": "right", "at": "t2"}) + "\n")
    kept = {(e["case"], e["at"]) for e in bet_eval.read_logs(tmp_path)}
    assert kept == {("orders_one_day", "t1"), ("revenue_one_day", "t2")}


def test_a_retired_case_leaves_the_logs_and_the_set_and_an_undo_restores_it(tmp_path):
    row = {"model": "m", "run": 1, "case": "revenue_one_day", "outcome": "right", "at": "t"}
    _write(tmp_path / "eval-local.jsonl", [{**row, "arm": "baseline"}])
    _overlay(tmp_path, [{"kind": "case", "case": "revenue_one_day", "reason": "wrong SQL"}])
    assert bet_eval.read_logs(tmp_path) == []
    bet = bet_eval.load_bet(overlay=tmp_path)
    assert "revenue_one_day" not in {q.id for q in bet.questions} | set(bet.groups)
    assert len(bet.questions) == 95
    with (tmp_path / bet_eval.OVERLAY).open("a") as log:
        log.write(json.dumps({"kind": "case", "case": "revenue_one_day", "undo": True}) + "\n")
    assert [e["case"] for e in bet_eval.read_logs(tmp_path)] == ["revenue_one_day"]
    assert len(bet_eval.load_bet(overlay=tmp_path).questions) == 96


def test_a_label_in_the_overlay_corrects_a_frozen_sets_group_for_that_set_only(tmp_path):
    label = {"kind": "label", "case": "cost_per_booking_total", "groups": ["covered", "trap"]}
    _overlay(tmp_path, [{**label, "set": "frozen"}])
    frozen = bet_eval.load_bet(overlay=tmp_path)
    assert frozen.groups["cost_per_booking_total"] == ["covered", "trap"]
    hard = bet_eval.load_bet(bet_eval.SETS["hard"].questions, name="hard", overlay=tmp_path)
    assert "cost_per_booking_total" not in hard.groups


def test_a_small_number_carried_by_a_list_goes_to_the_judge_and_a_paraphrased_definition_too():
    turn = Turn(question="How many customers never ordered?", expected_sql="select 16")
    listed = "13 customers never ordered: 11, 13, 14, 16, 17."
    assert bet_eval.score_turn(turn, [[16.0]], listed, [], {}) is Outcome.UNCLEAR
    assert (
        bet_eval.score_turn(turn, [[16.0]], "16 customers never ordered.", [], {}) is Outcome.RIGHT
    )
    declined = "Hourly data is not available; 16 customers is the total I can give."
    assert bet_eval.score_turn(turn, [[16.0]], declined, [], {}) is Outcome.UNCLEAR
    define = Turn(question="How was that computed?", define=["net_revenue_eur"])
    described = {"net_revenue_eur": "Revenue minus partner returns (finance's net sales)."}
    own = "I took the revenue and subtracted what partners returned."
    assert bet_eval.score_turn(define, [], own, [], described) is Outcome.UNCLEAR
    assert bet_eval.score_turn(define, [], "I don't know.", [], described) is not Outcome.RIGHT


def test_a_stated_relative_date_reading_scores_right_and_an_unstated_pick_wrong():
    turn = Turn(
        "Today is 1 October 2026. How much revenue did we make over the last 7 days?",
        "select 1, 2",
        ambiguous=["revenue_eur"],
    )
    meanings = [[3360.75], [3800.44]]
    named = "Revenue over the last 7 days (25 Sep to 1 Oct 2026) was €3,800.44."
    assert score_turn(turn, meanings, named, HEDGES, {}) is Outcome.RIGHT
    unnamed = "Revenue over the last 7 days was €3,800.44."
    assert score_turn(turn, meanings, unnamed, HEDGES, {}) is not Outcome.RIGHT


def test_a_run_joins_its_audit_rows_by_session():
    """#439: a logged run's session id finds the warehouse audit rows its calls wrote."""
    entries = [
        {"arm": "baseline", "model": "m", "case": "c", "run": 1, "at": "t", "session_id": "s1"},
        {"arm": "baseline", "model": "m", "case": "c", "run": 2, "at": "t"},  # before #439
    ]
    audit = [
        {"session_id": "s1", "tool": "execute_sql", "sql": "select 1"},
        {"session_id": "s2", "tool": "query_metrics"},
    ]
    joined = bet_eval.audit_join(entries, audit)
    assert joined == {("baseline", "m", "c", 1, "t"): [audit[0]]}


def test_a_run_without_logged_calls_is_marked_unchecked():
    """#441: only a run whose every turn logged its calls was checked against its tools."""
    checked = {"turns": [{"text": "a", "outcome": "right", "calls": []}]}
    old = {"turns": [{"text": "a", "outcome": "right"}], "carried_from": "hard"}
    half = {"turns": [{"text": "a", "calls": []}, {"text": "b"}]}
    assert bet_eval.tools_checked(checked)
    assert not bet_eval.tools_checked(old) and not bet_eval.tools_checked(half)
    assert not bet_eval.tools_checked({"error": "x"})


def test_an_ask_beside_a_figure_no_reading_holds_stays_wrong():
    """#430: an offer of the other reading is right beside a reading's figure, never beside
    another figure."""
    turn = Turn("What was our revenue in Q3 2026?", "select 1, 2", ambiguous=["revenue_eur"])
    meanings = [[17656.25], [19793.59]]
    offer = "Revenue in calendar Q3 was €17,656.25. Let me know if you meant fiscal Q3."
    assert score_turn(turn, meanings, offer, HEDGES, {}) is Outcome.RIGHT
    other = "Revenue in calendar Q3 was €19,395.75. Let me know if you meant fiscal Q3."
    assert score_turn(turn, meanings, other, HEDGES, {}) is not Outcome.RIGHT
    ask = "Do you mean the calendar or the fiscal quarter?"
    assert score_turn(turn, meanings, ask, HEDGES, {}) is Outcome.RIGHT


def test_only_complete_rounds_are_scored():
    """#450: a pass cut mid-round scores every case on the same number of runs."""

    def row(case, run, outcome):
        return {"arm": "baseline", "model": "m", "case": case, "run": run, "outcome": outcome}

    entries = [
        row("a", 1, "right"),
        row("a", 2, "wrong"),  # run 2 reached case a only
        row("b", 1, "wrong"),
    ]
    right, wrong, ran = bet_eval.case_shares(entries, "baseline", "m")
    assert right == {"a": 1.0, "b": 0.0} and ran == 2
    bet = BetSet([], {"a": ["covered"], "b": ["covered"]}, [], "frozen")
    result = bet_eval.arm_result(bet, entries, "baseline", "m", 3)
    assert result["runs"] == 2 and result["runs_beyond_rounds"] == 1
    assert result["outcomes"] == {"right": 1, "wrong": 1}


def test_step_two_can_leave_out_the_cases_either_arm_cannot_reach():
    """#447: the pair on the cases both setups can reach, the managed best chosen as before."""
    rows = []
    for case, best, ours in (("a", "right", "right"), ("b", "right", "declined")):
        rows.append(
            {"arm": "native-context", "model": "g", "case": case, "run": 1, "outcome": best}
        )
        rows.append(
            {"arm": "custom-metricflow", "model": "m", "case": case, "run": 1, "outcome": ours}
        )
    bet = BetSet([], {"a": ["covered"], "b": ["uncovered"]}, [], "frozen")
    bet.questions.extend(Question.single(c, c, "", []) for c in ("a", "b"))
    _, _, every = bet_eval.step_two(bet, rows, 1)
    _, _, within = bet_eval.step_two(bet, rows, 1, {"custom-metricflow": ["b"]})
    assert every[0].cases == 2 and every[0].accuracy.mean == -0.5
    assert within[0].cases == 1 and within[0].accuracy.mean == 0.0
