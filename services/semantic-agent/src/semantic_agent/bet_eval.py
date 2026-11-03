"""The semantic bet's local arms on the frozen set (docs/research/semantic-bet/RULE.md).

The two arms that need no GCP, `custom-metricflow` (the semantic agent on its MetricFlow tools) and
`baseline` (the text-to-SQL baseline), answer every case of `evals/semantic_bet.yaml` k times, each
run in a fresh session, on one model; each turn is scored under the bet's rule (bet_rule.py), never
by the eval's own pass/fail: a number turn is right only with its number (a decline never is), a
`define` or `ambiguous` turn by the eval's scorers, a turn that repeats or obeys a planted
instruction never.

Every finished run of a case is appended to a JSONL log as it finishes, so a spent quota or a cut
wake resumes where it stopped: a run already in the log is never asked again. The report is
rebuilt from the log alone (`--report-only`), into `docs/research/semantic-bet/eval-local.md`.

Usage (`make agent-eval ARM=bet` sets the env, after building the fixture):
  python -m semantic_agent.bet_eval [--runs 3] [--minutes 40] [--requests 300] [--report-only]
    [case ids]
The free tier's 1,000 requests a day are shared with other scheduled runs: a wake gives a pass a
`--requests` budget (each case's model responses, counted once it finishes) rather than spend them.
Exit 0: the report holds every run; 3: incomplete (the quota, a budget or the ids given cut it),
the report written from what the log holds.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from google.adk.agents import LlmAgent
from google.adk.evaluation.eval_case import Invocation

from semantic_agent import evaluation
from semantic_agent.bet_rule import (
    ArmScore,
    Outcome,
    arm_score,
    number_right,
    paired_interval,
    run_outcome,
    turn_outcome,
)
from semantic_agent.evaluation import (
    ANSWER_CORRECT,
    DECLINE,
    Expected,
    Question,
    Turn,
    _answer,
    _words,
    asks_or_gives_each,
    carries,
    numbers_in,
    obeys_or_repeats,
)

RESEARCH = evaluation.ROOT.parents[1] / "docs" / "research" / "semantic-bet"
LOG = RESEARCH / "eval-local.jsonl"
REPORT = RESEARCH / "eval-local.md"
RUNS = 3
# A run that errors (not a spent quota) is asked again once on a later pass; twice is scored wrong.
MAX_ERRORS = 2
# The two local arms, in the order a run asks them: the pair compared is baseline → metricflow.
ARMS = ("baseline", "custom-metricflow")


@dataclass(frozen=True)
class BetSet:
    """The frozen set: its cases, each case's groups and the hedge phrases."""

    questions: list[Question]
    groups: dict[str, list[str]]
    hedges: list[str]


def load_bet(path: Path = evaluation.BET_QUESTIONS, ids: Sequence[str] = ()) -> BetSet:
    spec = yaml.safe_load(path.read_text())
    return BetSet(evaluation.load_questions(list(ids), path), spec["groups"], spec["hedges"])


def score_turn(
    turn: Turn,
    numbers: list[list[float]],
    text: str,
    hedges: Sequence[str],
    described: Mapping[str, str],
    obeyed: bool = False,
) -> Outcome:
    """One turn's outcome under the rule.

    A `define` turn that fails to quote its definitions, or an `ambiguous` turn that picks one
    meaning silently, has no number outside tolerance to be confidently wrong about: wrong, or
    declined when it only declines. A planted instruction repeated or obeyed makes any turn wrong.
    """
    if obeyed:
        return Outcome.WRONG
    if turn.kind == "number":
        return turn_outcome(text, number_right(text, numbers), hedges)
    if turn.kind == "define":
        right = all(_words(described[name]) in _words(text) for name in turn.define)
    else:
        right = asks_or_gives_each(text, numbers)
        if not right and numbers_in(text) and not any(carries(text, m) for m in numbers):
            return turn_outcome(text, False, hedges)
    if right:
        return Outcome.RIGHT
    if not numbers_in(text) and DECLINE.search(text):
        return Outcome.DECLINED
    return Outcome.WRONG


def score_case(
    question: Question,
    expected: Expected,
    inferences: Sequence[Invocation],
    hedges: Sequence[str],
    described: Mapping[str, str],
) -> list[tuple[str, Outcome]]:
    """Each turn's answer (freshness statements left out) and outcome; a turn never answered is
    unclear."""
    scored = []
    for i, turn in enumerate(question.turns):
        if i >= len(inferences):
            scored.append(("", Outcome.UNCLEAR))
            continue
        text = _answer(inferences[i])
        obeyed = bool(turn.planted) and obeys_or_repeats(inferences[i], turn.planted)
        scored.append((text, score_turn(turn, expected[i], text, hedges, described, obeyed=obeyed)))
    return scored


def read_log(path: Path = LOG) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append_log(entry: dict[str, Any], path: Path = LOG) -> None:
    with path.open("a") as out:
        out.write(json.dumps(entry, ensure_ascii=False) + "\n")


def finished(entries: Sequence[dict[str, Any]], model: str) -> dict[tuple[str, int, str], str]:
    """The run outcome of every (arm, run, case) the log finished on this model: a scored run, or
    one that errored MAX_ERRORS times (wrong)."""
    done: dict[tuple[str, int, str], str] = {}
    errors: dict[tuple[str, int, str], int] = {}
    for e in entries:
        if e["model"] != model:
            continue
        key = (e["arm"], e["run"], e["case"])
        if e.get("error"):
            errors[key] = errors.get(key, 0) + 1
            if errors[key] >= MAX_ERRORS and key not in done:
                done[key] = Outcome.WRONG.value
        else:
            done[key] = e["outcome"]
    return done


async def run_bet(
    bet: BetSet,
    expected: Mapping[str, Expected],
    agents: Mapping[str, LlmAgent],
    described: Mapping[str, str],
    model: str,
    runs: int = RUNS,
    log: Path = LOG,
    deadline: float | None = None,
    requests: int | None = None,
) -> str:
    """Ask every (run, case, arm) the log has not finished, in that order, so a cut run still
    leaves both arms paired on the cases it reached. Returns why it stopped: `done`, `quota`
    (the model's quota or key ended the run), `time` (past the deadline) or `requests` (this pass
    spent its share of the shared free quota)."""
    spent = 0
    for run in range(1, runs + 1):
        for question in bet.questions:
            for arm in ARMS:
                if arm not in agents:
                    continue
                if (arm, run, question.id) in finished(read_log(log), model):
                    continue
                if deadline is not None and time.monotonic() > deadline:
                    return "time"
                if requests is not None and spent >= requests:
                    return "requests"
                semantic = arm == "custom-metricflow"
                cases = evaluation.eval_cases(
                    [question], dict(expected), agents[arm].name, semantic, dict(described)
                )
                outcome = (await evaluation.evaluate(agents[arm], cases, [ANSWER_CORRECT]))[
                    question.id
                ]
                spent += outcome.model_calls
                if outcome.skipped or outcome.ends_run:
                    return "quota"
                entry: dict[str, Any] = {
                    "arm": arm,
                    "model": model,
                    "run": run,
                    "case": question.id,
                    "at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "model_calls": outcome.model_calls,
                }
                if outcome.error:
                    entry["error"] = " ".join(outcome.error.split())[:300]
                    append_log(entry, log)
                    continue
                turns = score_case(
                    question, expected[question.id], outcome.inferences, bet.hedges, described
                )
                entry["turns"] = [{"text": t, "outcome": o.value} for t, o in turns]
                entry["outcome"] = run_outcome([o for _, o in turns]).value
                append_log(entry, log)
    return "done"


@dataclass(frozen=True)
class Scored:
    """What the report says for one model: the runs scored, each arm's score, the pair."""

    model: str
    runs: int  # runs per case scored (complete rounds, or 1 on the cases reached)
    cases: list[str]
    complete: bool
    scores: dict[str, ArmScore]
    requests: dict[str, int]
    finished: dict[str, int]  # runs finished per arm, of every case and round


def score_log(bet: BetSet, entries: Sequence[dict[str, Any]], model: str, runs: int) -> Scored:
    """Score complete rounds when every case has one for every arm; otherwise run 1 of the cases
    every arm reached (partial, described as such)."""
    done = finished(entries, model)
    ids = [q.id for q in bet.questions]
    arms = [a for a in ARMS if any(k[0] == a for k in done)]
    rounds = 0
    while rounds < runs and all((a, rounds + 1, c) in done for a in arms for c in ids):
        rounds += 1
    if rounds:
        cases, used = ids, rounds
    else:
        cases, used = [c for c in ids if all((a, 1, c) in done for a in arms)], 1
    groups = {c: bet.groups[c] for c in cases}
    scores = {
        a: arm_score(
            {c: [Outcome(done[(a, r, c)]) for r in range(1, used + 1)] for c in cases}, groups
        )
        for a in arms
        if cases
    }
    requests = {
        a: sum(e.get("model_calls", 0) for e in entries if e["model"] == model and e["arm"] == a)
        for a in arms
    }
    count = {a: sum(1 for k in done if k[0] == a) for a in arms}
    return Scored(model, used, cases, rounds == runs, scores, requests, count)


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def report(bet: BetSet, entries: Sequence[dict[str, Any]], runs: int = RUNS) -> str:
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")
    models = list(dict.fromkeys(e["model"] for e in entries))
    total = len(bet.questions) * runs
    lines = [
        "# The bet's local arms on the frozen set",
        "",
        f"Written {stamp} by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from "
        "[`eval-local.jsonl`](eval-local.jsonl), the log of every run, under "
        "[the rule](RULE.md): "
        f"{len(bet.questions)} cases of `services/semantic-agent/evals/semantic_bet.yaml`, "
        f"k = {runs} runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and "
        "`fixture_weeks.sql` in the Compose warehouse.",
        "`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the "
        "`legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads "
        "the generated docs.",
        "Unclear turns (no number parses and no decline) await the blind judge and count as "
        "wrong here.",
    ]
    if not models:
        lines += ["", "No run is logged yet."]
    for model in models:
        s = score_log(bet, entries, model, runs)
        state = (
            f"all {runs} runs of every case"
            if s.complete
            else f"partial: {s.runs} run(s) of {len(s.cases)} of {len(bet.questions)} cases"
        )
        lines += [
            "",
            f"## `{model}`",
            "",
            f"Scored on {state}; runs finished: "
            + ", ".join(f"{a} {s.finished[a]} of {total}" for a in s.finished)
            + "; model responses spent: "
            + ", ".join(f"{a} {s.requests[a]}" for a in s.requests)
            + ".",
        ]
        if not s.scores:
            lines += ["", "No case has a finished run on every arm yet."]
            continue
        arms = list(s.scores)
        names = sorted({g for c in s.cases for g in bet.groups[c]})
        lines += [
            "",
            "| | " + " | ".join(f"`{a}`" for a in arms) + " |",
            "|---|" + "---|" * len(arms),
            "| Accuracy | " + " | ".join(pct(s.scores[a].accuracy) for a in arms) + " |",
            "| Confident-wrong | "
            + " | ".join(pct(s.scores[a].confident_wrong) for a in arms)
            + " |",
            f"| pass^{s.runs} | " + " | ".join(pct(s.scores[a].pass_k) for a in arms) + " |",
        ]
        for name in names:
            n = sum(1 for c in s.cases if name in bet.groups[c])
            lines.append(
                f"| `{name}` ({n}) accuracy | "
                + " | ".join(pct(s.scores[a].groups[name]) for a in arms)
                + " |"
            )
        if set(ARMS) <= set(arms):
            a, b = s.scores["baseline"], s.scores["custom-metricflow"]
            acc = paired_interval(a.right, b.right)
            wrong = paired_interval(a.wrong_confidently, b.wrong_confidently)
            lines += [
                "",
                "Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% "
                "(10,000 resamples, seed 325):",
                "",
                f"- Accuracy: {acc.mean:+.3f} [{acc.low:+.3f}, {acc.high:+.3f}]: "
                + ("a difference." if acc.differs else "no difference."),
                f"- Confident-wrong: {wrong.mean:+.3f} [{wrong.low:+.3f}, {wrong.high:+.3f}]: "
                + ("a difference." if wrong.differs else "no difference."),
                "",
                "Both local arms are on rung 3 or 4 and none is the managed best, so this pair is "
                "descriptive (RULE.md § The rule, 5) until the native arms are scored (#333).",
            ]
        unclear = sorted({c for a in arms for c in s.scores[a].unclear})
        if unclear:
            lines += ["", "Cases with an unclear turn: " + ", ".join(f"`{c}`" for c in unclear)]
    errors = sorted({e["error"] for e in entries if e.get("error")})
    if errors:
        lines += ["", "## Errors", ""] + [f"- {e}" for e in errors]
    return "\n".join(lines) + "\n"


async def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m semantic_agent.bet_eval")
    parser.add_argument("ids", nargs="*", help="only these cases (the report still covers all)")
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument("--minutes", type=float, default=None, help="stop asking after this long")
    parser.add_argument(
        "--requests", type=int, default=None, help="stop once this pass spent this many requests"
    )
    parser.add_argument("--report-only", action="store_true", help="rewrite the report, ask none")
    args = parser.parse_args(argv)

    from semantic_agent.model import DEFAULT_MODEL_ID

    model = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    bet = load_bet()
    why = "report"
    if not args.report_only:
        from semantic_agent.agent import build_agent as build_semantic
        from sql_baseline.agent import build_agent as build_baseline

        asked = load_bet(ids=args.ids) if args.ids else bet
        database = os.environ.get("DBT_DBNAME", "dbt_dev")
        owner_url = os.environ.get(
            "WAREHOUSE_OWNER_URL", f"postgresql://warehouse:warehouse@localhost:5433/{database}"
        )
        expected = evaluation.expected_numbers(asked.questions, owner_url)
        described = evaluation.definitions(asked.questions)
        agents = {"baseline": build_baseline(), "custom-metricflow": build_semantic()}
        deadline = time.monotonic() + 60 * args.minutes if args.minutes else None
        why = await run_bet(
            asked, expected, agents, described, model, args.runs, LOG, deadline, args.requests
        )
    text = report(bet, read_log(), args.runs)
    REPORT.write_text(text)
    print(text)
    print(f"stopped: {why}; written to {REPORT}")
    complete = all(score_log(bet, read_log(), m, args.runs).complete for m in [model])
    return 0 if complete else 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
