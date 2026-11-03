"""The semantic bet's live arms on its sets (docs/research/semantic-bet/RULE.md).

The arms whose agent is a probe beside the findings (`native-mcp` on Google's MCP servers,
`custom-toolbox` on generated Toolbox tools) answer the frozen set the way the local arms do in
bet_eval.py: every turn of a conversation in one session, each run in a fresh one, each turn scored
with `bet_eval.score_case`, and every finished run appended to the arm's own log,
`docs/research/semantic-bet/eval-<arm>.jsonl` (`eval-hard-<arm>.jsonl` on the hard set), in
`eval-local.jsonl`'s shape, so `bet_eval.report` reads it beside the local pair and a cut pass
resumes where it stopped.

A run whose model call failed is left out of the log, so a later pass asks it again; a spent daily
quota, a refused key, a billing refusal or a spent Claude budget ends the pass, since no later call
can succeed until someone acts. On Claude (#361) each logged run carries its token usage and
dollars (spend.METER); the caller opens the pass with `spend.METER.start(label, dollars)` and closes
it with `spend.finish_pass()`.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.evaluation.eval_case import Invocation
from google.adk.runners import InMemoryRunner
from google.genai import types

from semantic_agent import spend
from semantic_agent.bet_eval import (
    FROZEN,
    RESEARCH,
    RUNS,
    SETS,
    BetSet,
    append_log,
    finished,
    read_log,
    score_case,
)
from semantic_agent.bet_rule import run_outcome
from semantic_agent.evaluation import Expected, model_responses
from semantic_agent.model import failure_of

# Each tool result kept in the log is cut to this many characters.
RESULT_HEAD = 400
# A conversation: its turns' questions in, one dict per turn answered out (`converse`'s shape).
Converse = Callable[[Sequence[str]], Awaitable[list[dict[str, Any]]]]
# The failures after which no later call can succeed this pass (ModelFailure.ends_run).
FATAL = ("daily_quota", "auth", "billing", "budget")


def log_path(arm: str, directory: Path = RESEARCH, name: str = FROZEN) -> Path:
    """The arm's log on one set: `eval-<arm>.jsonl` (the frozen set), `eval-hard-<arm>.jsonl`."""
    return SETS[name].arm_log(arm, directory)


async def converse(agent: LlmAgent, questions: Sequence[str]) -> list[dict[str, Any]]:
    """Ask every question in one session, in order, as a user's follow-ups.

    Each turn: its question, every tool call with its arguments and result head, the answer, the
    model's reasoning (ADK's thought parts, kept apart and never scored), its model responses, and
    `failure` when a model call failed; the conversation stops after a failed turn.
    """
    runner = InMemoryRunner(agent=agent, app_name=agent.name)
    session = await runner.session_service.create_session(app_name=agent.name, user_id="bet")
    turns: list[dict[str, Any]] = []
    try:
        for question in questions:
            # By function-call id: parallel calls answer out of order.
            calls: dict[str, dict[str, Any]] = {}
            answer = ""
            thought = ""
            events = []
            message = types.Content(role="user", parts=[types.Part(text=question)])
            async for event in runner.run_async(
                user_id="bet", session_id=session.id, new_message=message
            ):
                events.append(event)
                for part in (event.content.parts if event.content else None) or []:
                    if part.function_call:
                        calls[part.function_call.id or str(len(calls))] = {
                            "tool": part.function_call.name,
                            "args": dict(part.function_call.args or {}),
                        }
                    elif part.function_response and part.function_response.id in calls:
                        calls[part.function_response.id]["result"] = json.dumps(
                            part.function_response.response, default=str
                        )[:RESULT_HEAD]
                    elif part.text and part.thought:
                        thought += part.text
                    elif part.text and event.is_final_response():
                        answer += part.text
            turn: dict[str, Any] = {
                "question": question,
                "calls": list(calls.values()),
                "answer": answer.strip(),
                "thought": thought.strip(),
                "model_calls": model_responses(events),
            }
            # A failed model call ends the turn with an answer naming it: never score that.
            if failure := failure_of(events):
                turn["failure"] = dataclasses.asdict(failure)
            turns.append(turn)
            if "failure" in turn:
                break
    finally:
        await runner.close()
    return turns


def _invocation(turn: dict[str, Any]) -> Invocation:
    """A turn's answer as the eval's scorers read it (no tool data: a probe's calls are not the
    semantic agent's `query_metrics`)."""
    return Invocation(
        user_content=types.Content(role="user", parts=[types.Part(text=turn["question"])]),
        final_response=types.Content(role="model", parts=[types.Part(text=turn["answer"])]),
    )


async def run_live(
    bet: BetSet,
    expected: Mapping[str, Expected],
    described: Mapping[str, str],
    arm: str,
    ask: Converse,
    model: str,
    runs: int = RUNS,
    log: Path | None = None,
    deadline: float | None = None,
    requests: int | None = None,
    say: Callable[[str], None] = print,
) -> str:
    """Ask every (run, case) the arm's log has not finished, run 1 of every case first, so a cut
    pass leaves whole rounds behind it. Returns why it stopped: `done`, `quota` (the model's daily
    quota or key), `time` (past the deadline), `requests` (this pass spent its budget) or `budget`
    (its Claude dollars)."""
    log = log or log_path(arm)
    spent = 0
    for run in range(1, runs + 1):
        for question in bet.questions:
            entries = [{"arm": arm, **e} for e in read_log(log)]
            if (arm, run, question.id) in finished(entries, model):
                continue
            if deadline is not None and time.monotonic() > deadline:
                return "time"
            if requests is not None and spent >= requests:
                return "requests"
            if not spend.METER.room_for_case():
                return "budget"
            mark = spend.METER.begin_case(model, arm=arm, run=run, case=question.id)
            turns = await ask([t.question for t in question.turns])
            usage = spend.METER.end_case(mark)
            spent += sum(t.get("model_calls", 0) for t in turns)
            failed = next((t["failure"] for t in turns if t.get("failure")), None)
            if failed:
                say(f"{question.id} run {run}: not logged, the model call failed: {failed}")
                if failed["kind"] == "budget":
                    return "budget"
                if failed["kind"] in FATAL:
                    return "quota"
                continue
            scored = score_case(
                question,
                expected[question.id],
                [_invocation(t) for t in turns],
                bet.hedges,
                described,
            )
            outcome = run_outcome([o for _, o in scored])
            append_log(
                {
                    "arm": arm,
                    "model": model,
                    "run": run,
                    "case": question.id,
                    "at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "model_calls": sum(t["model_calls"] for t in turns),
                    **({"usage": usage.as_dict()} if usage.calls else {}),
                    "turns": [
                        {"text": text, "outcome": o.value, "calls": t["calls"]}
                        for (text, o), t in zip(scored, turns, strict=False)
                    ],
                    "outcome": outcome.value,
                },
                log,
            )
            tools = [[c["tool"] for c in t["calls"]] for t in turns]
            say(f"{question.id} run {run}: {outcome.value} {tools}")
    return "done"
