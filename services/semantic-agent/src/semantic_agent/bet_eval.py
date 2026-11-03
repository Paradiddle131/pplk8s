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

A turn the code cannot decide (unclear) goes to the blind judge (`--judge`, RULE.md § Scoring a
run): a free model asked twice, shown the question, the expected number and the answer, never the
arm. Each verdict is appended to `judge.jsonl` beside the arms' logs, keyed by the turn and a hash
of its answer, so a rescore or a second pass spends nothing; the arms' logs are never rewritten for
it (other passes append to them at the same time), and every report applies the verdicts on read.

Usage (`make agent-eval ARM=bet` sets the env, after building the fixture):
  python -m semantic_agent.bet_eval [--runs 3] [--minutes 40] [--requests 300]
    [--report-only | --rescore | --judge] [case ids]
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
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from google.adk.agents import LlmAgent
from google.adk.evaluation.eval_case import Invocation
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from semantic_agent import evaluation
from semantic_agent.bet_rule import (
    ArmScore,
    Outcome,
    answer_hash,
    arm_score,
    declines,
    judge_prompt,
    number_right,
    paired_interval,
    parse_verdict,
    run_outcome,
    stated,
    turn_outcome,
    two_verdicts,
)
from semantic_agent.evaluation import (
    ANSWER_CORRECT,
    Expected,
    Question,
    Turn,
    _answer,
    _words,
    asks_or_gives_each,
    carries,
    obeys_or_repeats,
)

RESEARCH = evaluation.ROOT.parents[1] / "docs" / "research" / "semantic-bet"
LOG = RESEARCH / "eval-local.jsonl"
REPORT = RESEARCH / "eval-local.md"
# Every arm's scores side by side, from eval-local.jsonl and each live arm's eval-<arm>.jsonl.
ALL_REPORT = RESEARCH / "eval.md"
# The blind judge's verdicts, one line each, beside the logs (never in them: other passes append
# to the arms' logs while the judge runs).
JUDGE_LOG = RESEARCH / "judge.jsonl"
# RULE.md: the judge decides twice.
VERDICTS = 2
RUNS = 3
# A run that errors (not a spent quota) is asked again once on a later pass; twice is scored wrong.
MAX_ERRORS = 2
# The two local arms, in the order a run asks them: the pair compared is baseline → metricflow.
ARMS = ("baseline", "custom-metricflow")
# RULE.md's cost ladder: rungs 1 and 2 are managed agents, 3 and 4 are ours; a tie goes lower.
RUNG = {
    "native-context": 1,
    "native-kc": 1,
    "native-governed": 2,
    "native-shaped": 2,
    "native-graph": 2,
    "native-mcp": 3,
    "custom-toolbox": 3,
    "custom-metricflow": 4,
}


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
        return turn_outcome(text, number_right(text, numbers), hedges, turn.question)
    if turn.kind == "define":
        right = all(_words(described[name]) in _words(text) for name in turn.define)
    else:
        right = asks_or_gives_each(text, numbers)
        own = stated(text, turn.question)
        if not right and own and not any(carries(text, m) for m in numbers):
            return turn_outcome(text, False, hedges, turn.question)
    if right:
        return Outcome.RIGHT
    if not stated(text, turn.question) and declines(text):
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


def rescore(
    bet: BetSet,
    entries: Sequence[dict[str, Any]],
    expected: Mapping[str, Expected],
    described: Mapping[str, str],
) -> list[dict[str, Any]]:
    """The log's runs scored again from their answers' text, after the scoring code changed: no
    model is asked. A planted turn keeps its logged outcome (whether a tool call obeyed it is not
    in the log)."""
    questions = {q.id: q for q in bet.questions}
    out = []
    for e in entries:
        e = dict(e)
        if e.get("turns") and e["case"] in questions:
            q = questions[e["case"]]
            turns = []
            for i, (turn, logged) in enumerate(zip(q.turns, e["turns"], strict=True)):
                outcome = (
                    Outcome(logged["outcome"])
                    if turn.planted
                    else score_turn(turn, expected[q.id][i], logged["text"], bet.hedges, described)
                )
                turns.append({**logged, "outcome": outcome.value})
            e["turns"] = turns
            e["outcome"] = run_outcome([Outcome(t["outcome"]) for t in turns]).value
        out.append(e)
    return out


def read_log(path: Path = LOG) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def read_logs(directory: Path = RESEARCH) -> list[dict[str, Any]]:
    """Every arm's runs: the local arms' log, then each `eval-<arm>.jsonl` beside it, whose rows
    take the arm from the file name when they do not name one."""
    entries = read_log(directory / LOG.name)
    for path in sorted(directory.glob("eval-*.jsonl")):
        if path.name == LOG.name:
            continue
        arm = path.stem.removeprefix("eval-")
        entries += [{"arm": arm, **e} for e in read_log(path)]
    return entries


# A blind judge: a prompt in, the model's text out (bet_rule.judge_prompt, parse_verdict).
Judge = Callable[[str], Awaitable[str]]
# A turn's place in the logs: arm, the arm's model, case, run and turn index.
TurnKey = tuple[str, str, str, int, int]


def model_judge() -> Judge:
    """The judge on the model factory's judge model (model.build_judge), one request per call."""
    from semantic_agent.model import build_judge

    llm = build_judge()

    async def ask(prompt: str) -> str:
        request = LlmRequest(
            model=llm.model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(),
        )
        text = ""
        async for response in llm.generate_content_async(request, stream=False):
            parts = response.content.parts if response.content else None
            text += "".join(p.text or "" for p in parts or [] if not p.thought)
        return text

    return ask


def unclear_turns(entries: Sequence[dict[str, Any]]) -> list[tuple[TurnKey, str]]:
    """Every turn the code left unclear, with its answer's text, in log order."""
    found = []
    for e in entries:
        for i, turn in enumerate(e.get("turns") or []):
            if turn["outcome"] == Outcome.UNCLEAR.value:
                found.append(((e["arm"], e["model"], e["case"], e["run"], i), turn["text"]))
    return found


def read_verdicts(path: Path = JUDGE_LOG, judge: str | None = None) -> dict[tuple, list[Any]]:
    """The cached verdicts, by (turn key, answer hash): each attempt's verdict (None when the judge
    gave none), only those of this judge model when one is named."""
    verdicts: dict[tuple, list[Any]] = {}
    for row in read_log(path):
        if judge is not None and row["judge"] != judge:
            continue
        key = (row["arm"], row["model"], row["case"], row["run"], row["turn"], row["answer"])
        attempts = verdicts.setdefault(key, [None] * VERDICTS)
        attempts[row["n"] - 1] = row["verdict"] or ""
    return verdicts


def apply_verdicts(
    entries: Sequence[dict[str, Any]], verdicts: Mapping[tuple, list[Any]]
) -> list[dict[str, Any]]:
    """The logs' runs with each unclear turn's two verdicts applied: equal verdicts stand, different
    ones leave it unclear; the turn keeps its verdicts (`judged`) and the run is scored again."""
    out = []
    for e in entries:
        turns = e.get("turns") or []
        if not any(t["outcome"] == Outcome.UNCLEAR.value for t in turns):
            out.append(e)
            continue
        judged = []
        for i, turn in enumerate(turns):
            key = (e["arm"], e["model"], e["case"], e["run"], i, answer_hash(turn["text"]))
            attempts = verdicts.get(key)
            if turn["outcome"] != Outcome.UNCLEAR.value or not attempts or None in attempts:
                judged.append(turn)
                continue
            first, second = (Outcome(v) if v else None for v in attempts)
            outcome = two_verdicts(first, second)
            judged.append({**turn, "outcome": outcome.value, "judged": list(attempts)})
        out.append(
            {**e, "turns": judged, "outcome": run_outcome([Outcome(t["outcome"]) for t in judged])}
        )
    return out


async def judge_turns(
    bet: BetSet,
    entries: Sequence[dict[str, Any]],
    expected: Mapping[str, Expected],
    judge: Judge,
    judge_model: str,
    path: Path = JUDGE_LOG,
    requests: int | None = None,
) -> tuple[str, int]:
    """Ask the judge each verdict the cache lacks for an unclear turn, appending each to `path` as
    it comes; returns why it stopped (`done`, `requests` or `quota`) and the requests sent."""
    from semantic_agent.model import classify

    questions = {q.id: q for q in bet.questions}
    spent = 0
    for (arm, model, case, run, i), text in unclear_turns(entries):
        if case not in questions:
            continue
        digest = answer_hash(text)
        key = (arm, model, case, run, i, digest)
        cached = read_verdicts(path, judge_model).get(key, [None] * VERDICTS)
        for n in range(1, VERDICTS + 1):
            if cached[n - 1] is not None:
                continue
            if requests is not None and spent >= requests:
                return "requests", spent
            prompt = judge_prompt(questions[case].turns[i].question, expected[case][i], text)
            spent += 1
            try:
                reply = await judge(prompt)
            except Exception as error:  # a failed request: asked again on a later pass
                if classify(error).ends_run:
                    return "quota", spent
                continue
            verdict = parse_verdict(reply)
            row = {
                "arm": arm,
                "model": model,
                "case": case,
                "run": run,
                "turn": i,
                "answer": digest,
                "judge": judge_model,
                "n": n,
                "verdict": verdict.value if verdict else None,
                "reply": " ".join(reply.split())[-300:],
                "at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            append_log(row, path)
    return "done", spent


def judged_logs(directory: Path = RESEARCH) -> list[dict[str, Any]]:
    """Every arm's runs with the current judge model's verdicts applied."""
    from semantic_agent.model import judge_model_id

    verdicts = read_verdicts(directory / JUDGE_LOG.name, judge_model_id())
    return apply_verdicts(read_logs(directory), verdicts)


def arms_of(entries: Sequence[dict[str, Any]], model: str) -> list[str]:
    """The arms logged on this model: the local pair first, then in the order they appear."""
    seen = list(dict.fromkeys(e["arm"] for e in entries if e["model"] == model))
    return [a for a in ARMS if a in seen] + [a for a in seen if a not in ARMS]


def managed_comparison(scores: Mapping[str, ArmScore]) -> list[str]:
    """RULE.md § The rule, 1 and 2: the managed best, and whether each arm of ours beats it."""
    managed = [a for a in scores if RUNG.get(a, 9) <= 2]
    if not managed:
        return []
    best = max(managed, key=lambda a: (scores[a].accuracy, -RUNG[a]))
    lines = [
        "",
        f"The managed best (RULE.md § The rule, 1): `{best}`, "
        f"accuracy {pct(scores[best].accuracy)}.",
    ]
    ours = [a for a in scores if RUNG.get(a, 9) in (3, 4)]
    if not ours:
        return [
            *lines,
            "No arm of ours (rung 3 or 4) ran on this model: nothing to compare it with.",
        ]
    lines += [
        "Paired by case against it, percentile bootstrap 95% (10,000 resamples, seed 325):",
        "",
    ]
    for arm in ours:
        acc = paired_interval(scores[best].right, scores[arm].right)
        wrong = paired_interval(scores[best].wrong_confidently, scores[arm].wrong_confidently)
        worth = (acc.differs and acc.mean > 0) or (
            not acc.differs and wrong.differs and wrong.mean < 0
        )
        verdict = (
            "worth building (RULE.md § The rule, 2)." if worth else "not worth building on this."
        )
        lines.append(
            f"- `{arm}` (rung {RUNG[arm]}): accuracy {acc.mean:+.3f} [{acc.low:+.3f}, "
            f"{acc.high:+.3f}], confident-wrong {wrong.mean:+.3f} [{wrong.low:+.3f}, "
            f"{wrong.high:+.3f}]: " + verdict
        )
    return lines


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
    arms = [a for a in arms_of(entries, model) if any(k[0] == a for k in done)]
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


def judge_lines(entries: Sequence[dict[str, Any]], model: str) -> list[str]:
    """The judged turns on this model, and every turn still unclear after judging."""
    rows = [e for e in entries if e["model"] == model]
    judged = [t for e in rows for t in e.get("turns") or [] if "judged" in t]
    unclear = [
        (e, i, t)
        for e in rows
        for i, t in enumerate(e.get("turns") or [])
        if t["outcome"] == Outcome.UNCLEAR.value
    ]
    lines = []
    if judged:
        stood = sum(t["outcome"] != Outcome.UNCLEAR.value for t in judged)
        lines += ["", f"Turns judged: {len(judged)}; verdicts that stood: {stood}."]
    if unclear:
        lines += ["", "Turns still unclear after judging (counted as wrong):", ""]
        for e, i, t in sorted(unclear, key=lambda x: (x[0]["arm"], x[0]["case"], x[0]["run"])):
            verdicts = (
                " / ".join(v or "no verdict" for v in t["judged"])
                if "judged" in t
                else "not judged yet"
            )
            lines.append(f"- `{e['arm']}` `{e['case']}` run {e['run']} turn {i + 1}: {verdicts}")
    return lines


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def report(
    bet: BetSet, entries: Sequence[dict[str, Any]], runs: int = RUNS, every_arm: bool = False
) -> str:
    """eval-local.md (the local pair), or with `every_arm` eval.md: every logged arm side by side,
    the rule's comparison against the managed best, and how far each arm got."""
    from semantic_agent.model import judge_model_id

    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")
    models = list(dict.fromkeys(e["model"] for e in entries))
    total = len(bet.questions) * runs
    title, source = (
        (
            "# Every arm on the frozen set",
            "[`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl`",
        )
        if every_arm
        else (
            "# The bet's local arms on the frozen set",
            "[`eval-local.jsonl`](eval-local.jsonl), the log of every run,",
        )
    )
    lines = [
        title,
        "",
        f"Written {stamp} by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from "
        f"{source} under "
        "[the rule](RULE.md): "
        f"{len(bet.questions)} cases of `services/semantic-agent/evals/semantic_bet.yaml`, "
        f"k = {runs} runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and "
        "`fixture_weeks.sql` in the Compose warehouse.",
        "Arms are compared on one model, paired on the cases every arm reached.",
        "`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the "
        "`legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads "
        "the generated docs.",
        f"A turn the code cannot decide (no number parses and no decline) goes to the blind "
        f"judge, `{judge_model_id()}` asked {VERDICTS} times ([`judge.jsonl`](judge.jsonl), "
        "RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong "
        "and is listed under its model.",
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
                "descriptive (RULE.md § The rule, 5) until the native arms are scored.",
            ]
        lines += managed_comparison(s.scores)
        lines += judge_lines(entries, model)
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
    parser.add_argument(
        "--rescore", action="store_true", help="score the log's answers again, ask none"
    )
    parser.add_argument("--report-only", action="store_true", help="rewrite the report, ask none")
    parser.add_argument(
        "--judge", action="store_true", help="ask the blind judge about every unclear turn"
    )
    args = parser.parse_args(argv)

    from semantic_agent.model import DEFAULT_MODEL_ID, judge_model_id

    model = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    bet = load_bet()
    why = "report"
    if args.judge:
        pending = {key[2] for key, _ in unclear_turns(read_logs())}
        asked = load_bet(ids=sorted(pending)) if pending else BetSet([], {}, [])
        database = os.environ.get("DBT_DBNAME", "dbt_dev")
        owner_url = os.environ.get(
            "WAREHOUSE_OWNER_URL", f"postgresql://warehouse:warehouse@localhost:5433/{database}"
        )
        expected = evaluation.expected_numbers(asked.questions, owner_url) if pending else {}
        why, spent = await judge_turns(
            asked, read_logs(), expected, model_judge(), judge_model_id(), JUDGE_LOG, args.requests
        )
        print(f"judge: {spent} request(s) sent to {judge_model_id()}")
    elif args.rescore:
        database = os.environ.get("DBT_DBNAME", "dbt_dev")
        owner_url = os.environ.get(
            "WAREHOUSE_OWNER_URL", f"postgresql://warehouse:warehouse@localhost:5433/{database}"
        )
        expected = evaluation.expected_numbers(bet.questions, owner_url)
        entries = rescore(bet, read_log(), expected, evaluation.definitions(bet.questions))
        LOG.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
        why = "rescored"
    elif not args.report_only:
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
    verdicts = read_verdicts(JUDGE_LOG, judge_model_id())
    text = report(bet, apply_verdicts(read_log(), verdicts), args.runs)
    REPORT.write_text(text)
    print(text)
    print(f"stopped: {why}; written to {REPORT}")
    ALL_REPORT.write_text(report(bet, judged_logs(), args.runs, every_arm=True))
    print(f"every arm: written to {ALL_REPORT}")
    if args.judge:
        return 0 if why == "done" else 3
    complete = all(score_log(bet, read_log(), m, args.runs).complete for m in [model])
    return 0 if complete else 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
