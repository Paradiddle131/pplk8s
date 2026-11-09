"""The bet's live arms (bet_live.py): conversations through a scripted model, runs through a
scripted probe; no warehouse, no MCP server, no live model."""

import asyncio

from google.adk.agents import LlmAgent

from semantic_agent import bet_eval, bet_live
from semantic_agent.bet_eval import BetSet
from semantic_agent.evaluation import Question, Turn, as_expected
from semantic_agent.model import answer_model_failure
from tests.conftest import ScriptedLlm
from tests.test_model_failures import rate_limit_error

REVENUE = Question.single("revenue_one_day", "Revenue on 2 October 2026?", "", ["revenue_eur"])
# A multi-turn case: a number, then its definition, in one session.
DEFINE = Question(
    "revenue_then_define",
    [
        Turn("Revenue on 2 October 2026?", metrics=["revenue_eur"]),
        Turn("How was that computed?", define=["revenue_eur"]),
    ],
)
BET = BetSet(
    [REVENUE, DEFINE],
    {"revenue_one_day": ["covered"], "revenue_then_define": ["covered", "multi-turn"]},
    ["approximately"],
)
EXPECTED = {
    "revenue_one_day": [[as_expected(868.65)]],
    "revenue_then_define": [[as_expected(868.65)], []],
}
DESCRIBED = {"revenue_eur": "Revenue in EUR of orders not cancelled."}
RIGHT = "Revenue was 868.65 EUR on 2 October 2026."
DEFINED = "Revenue is revenue in EUR of orders not cancelled."


class QuotaAfter(ScriptedLlm):
    """Answers its steps, then reports the free tier's daily quota spent."""

    async def generate_content_async(self, llm_request, stream=False):
        if len(self.requests) >= len(self.steps):
            raise rate_limit_error("free-models-per-day", 6 * 3600)
        async for response in super().generate_content_async(llm_request, stream):
            yield response


def agent(model: ScriptedLlm) -> LlmAgent:
    return LlmAgent(
        name="bet_probe", model=model, instruction="", on_model_error_callback=answer_model_failure
    )


def test_a_conversation_keeps_every_turn_in_one_session():
    model = ScriptedLlm(steps=[RIGHT, DEFINED])
    turns = asyncio.run(bet_live.converse(agent(model), ["Revenue?", "How was that computed?"]))
    assert [t["answer"] for t in turns] == [RIGHT, DEFINED]
    assert [t["model_calls"] for t in turns] == [1, 1]
    assert all("failure" not in t for t in turns)
    # The follow-up is asked with the first turn's question and answer before it.
    seen = [p.text for c in model.requests[1].contents for p in c.parts or [] if p.text]
    assert seen[:2] == ["Revenue?", RIGHT]


def test_a_conversation_stops_at_the_turn_whose_model_call_failed():
    turns = asyncio.run(
        bet_live.converse(agent(QuotaAfter(steps=[RIGHT])), ["Revenue?", "Defined how?", "And?"])
    )
    assert len(turns) == 2
    assert "failure" not in turns[0] and turns[1]["failure"]["kind"] == "daily_quota"


class Probe:
    """A scripted probe: answers each conversation from `answers` (one list per call), counting
    the conversations it was asked."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.asked: list[list[str]] = []

    async def __call__(self, questions):
        self.asked.append(list(questions))
        texts = self.answers.pop(0)
        if isinstance(texts, dict):  # a failed model call
            failed = {"question": questions[0], "calls": [], "answer": "", "failure": texts}
            return [{**failed, "model_calls": 1}]
        return [
            {"question": q, "calls": [{"tool": "search_entries"}], "answer": a, "model_calls": 2}
            for q, a in zip(questions, texts, strict=True)
        ]


def run(probe: Probe, log, runs: int = 1, requests: int | None = None) -> str:
    return asyncio.run(
        bet_live.run_live(
            BET,
            EXPECTED,
            DESCRIBED,
            "native-mcp",
            probe,
            "m",
            runs,
            log,
            requests=requests,
            say=lambda line: None,
        )
    )


def test_every_turn_of_a_multi_turn_case_is_scored_and_logged_in_the_local_shape(tmp_path):
    log = tmp_path / "eval-native-mcp.jsonl"
    probe = Probe([[RIGHT], [RIGHT, DEFINED]])
    assert run(probe, log) == "done"
    assert probe.asked[1] == ["Revenue on 2 October 2026?", "How was that computed?"]
    rows = bet_eval.read_log(log)
    assert [(r["arm"], r["run"], r["case"], r["outcome"]) for r in rows] == [
        ("native-mcp", 1, "revenue_one_day", "right"),
        ("native-mcp", 1, "revenue_then_define", "right"),
    ]
    assert rows[1]["model_calls"] == 4
    assert rows[1]["turns"] == [
        {"text": RIGHT, "outcome": "right", "calls": [{"tool": "search_entries"}]},
        {"text": DEFINED, "outcome": "right", "calls": [{"tool": "search_entries"}]},
    ]
    # The log reads beside the others, named by its file.
    assert [e["arm"] for e in bet_eval.read_logs(tmp_path)] == ["native-mcp", "native-mcp"]


def test_a_follow_up_without_its_definition_leaves_the_whole_run_to_the_judge(tmp_path):
    # #382: a definition not quoted word for word is the blind judge's to read, so the run is
    # unclear (counted as wrong) until judged, never right.
    log = tmp_path / "eval-native-mcp.jsonl"
    run(Probe([[RIGHT], [RIGHT, "It is the revenue."]]), log)
    rows = bet_eval.read_log(log)
    assert [t["outcome"] for t in rows[1]["turns"]] == ["right", "unclear"]
    assert rows[1]["outcome"] == "unclear"


def test_a_pass_resumes_from_the_log_and_stops_on_its_budget(tmp_path):
    log = tmp_path / "eval-native-mcp.jsonl"
    # Two requests a case: a budget of 2 asks one case, then stops.
    assert run(Probe([[RIGHT]]), log, runs=2, requests=2) == "requests"
    probe = Probe([[RIGHT, DEFINED], [RIGHT], [RIGHT, DEFINED]])
    assert run(probe, log, runs=2) == "done"
    assert len(probe.asked) == 3
    rows = bet_eval.read_log(log)
    assert [(r["run"], r["case"]) for r in rows] == [
        (1, "revenue_one_day"),
        (1, "revenue_then_define"),
        (2, "revenue_one_day"),
        (2, "revenue_then_define"),
    ]


def test_a_failed_call_is_left_out_and_a_spent_quota_ends_the_pass(tmp_path):
    log = tmp_path / "eval-native-mcp.jsonl"
    error = {"kind": "error", "message": "upstream 502", "retry_after_s": None}
    quota = {"kind": "daily_quota", "message": "spent", "retry_after_s": None}
    probe = Probe([error, quota])
    assert run(probe, log) == "quota"
    assert len(probe.asked) == 2 and not log.exists()
    # The next pass asks both cases again.
    assert run(Probe([[RIGHT], [RIGHT, DEFINED]]), log) == "done"
    assert len(bet_eval.read_log(log)) == 2


def test_each_set_logs_an_arm_to_its_own_file(tmp_path):
    assert bet_live.log_path("native-kc", tmp_path).name == "eval-native-kc.jsonl"
    assert bet_live.log_path("native-kc", tmp_path, "hard").name == "eval-hard-native-kc.jsonl"


def run_with_canary(probe: Probe, log) -> str:
    return asyncio.run(
        bet_live.run_live(
            BET,
            EXPECTED,
            DESCRIBED,
            "native-mcp",
            probe,
            "m",
            1,
            log,
            say=lambda line: None,
            canary=True,
        )
    )


def test_a_canary_missed_twice_stops_the_pass_before_any_run_is_logged(tmp_path):
    log = tmp_path / "eval-native-mcp.jsonl"
    broken = "The audit record could not be written, so the result was withheld."
    probe = Probe([[broken], [broken]])
    assert run_with_canary(probe, log) == "canary"
    assert len(probe.asked) == 2 and not log.exists()


def test_a_canary_answered_right_lets_the_pass_run(tmp_path):
    log = tmp_path / "eval-native-mcp.jsonl"
    probe = Probe([[RIGHT], [RIGHT], [RIGHT, DEFINED]])
    assert run_with_canary(probe, log) == "done"
    assert len(bet_eval.read_log(log)) == 2  # the canary is never logged


def test_a_setup_named_in_canary_set_takes_that_sets_canary(monkeypatch, tmp_path):
    # custom-lightdash cannot reach the hard sets' canary (no channel on its bookings explore),
    # so its hard pass checks health on the frozen canary; the hard case is still asked and scored.
    frozen = BetSet([REVENUE], {"revenue_one_day": ["covered"]}, ["approximately"])
    orders = Question.single("orders_one_day", "Orders on 2 October 2026?", "", ["orders_total"])
    hard = BetSet([orders], {"orders_one_day": ["covered"]}, ["approximately"], name="hard")
    monkeypatch.setattr(bet_eval, "load_set", lambda name: frozen)
    monkeypatch.setattr(
        bet_eval, "read_expected", lambda name: {"revenue_one_day": [[as_expected(868.65)]]}
    )
    monkeypatch.setattr(bet_eval.evaluation, "definitions", lambda questions: {})
    log = tmp_path / "eval-hard-custom-lightdash.jsonl"
    probe = Probe([[RIGHT], ["We got 41 orders on 2 October 2026."]])
    why = asyncio.run(
        bet_live.run_live(
            hard,
            {"orders_one_day": [[as_expected(41)]]},
            {},
            "custom-lightdash",
            probe,
            "m",
            1,
            log,
            say=lambda line: None,
            canary=True,
        )
    )
    assert why == "done"
    # The frozen canary first, then the hard set's own case (the scripted probe's calls are
    # native-mcp's, so the run goes to faults rather than the log; the order is what is tested).
    assert probe.asked == [["Revenue on 2 October 2026?"], ["Orders on 2 October 2026?"]]


def test_other_setups_keep_their_sets_canary():
    probe, probe_set, _, _ = bet_eval.arm_canary(BET, "native-mcp", EXPECTED, DESCRIBED)
    assert probe is REVENUE and probe_set is BET


def test_a_logged_run_keeps_its_session_and_each_turns_trace(tmp_path):
    """#439, #440: the session id on the run; each turn's invocation id, reasoning, result heads
    and BigQuery jobs beside its answer, never scored."""
    turns = asyncio.run(bet_live.converse(agent(ScriptedLlm(steps=[RIGHT])), ["Revenue?"]))
    assert turns[0]["session_id"] and turns[0]["invocation_id"]

    async def traced(questions):
        return [
            {
                "question": questions[0],
                "calls": [],
                "answer": RIGHT,
                "model_calls": 1,
                "session_id": "s-1",
                "invocation_id": "e-1",
                "thought": "Sum the day's orders.",
                "results": [[{"revenue": 868.65}]],
                "jobs": ["job_1"],
            }
        ]

    log = tmp_path / "eval-native-context.jsonl"
    bet = BetSet([REVENUE], {"revenue_one_day": ["covered"]}, [])
    asyncio.run(
        bet_live.run_live(
            bet, EXPECTED, DESCRIBED, "native-context", traced, "m", 1, log, say=lambda _: None
        )
    )
    (row,) = bet_eval.read_log(log)
    assert row["session_id"] == "s-1" and row["outcome"] == "right"
    assert row["turns"][0] | {} == {
        "text": RIGHT,
        "outcome": "right",
        "calls": [],
        "thought": "Sum the day's orders.",
        "invocation_id": "e-1",
        "results": [[{"revenue": 868.65}]],
        "jobs": ["job_1"],
    }
