"""The semantic bet's local arms on its sets (docs/research/semantic-bet/RULE.md).

The two arms that need no GCP, `custom-metricflow` (the semantic agent on its MetricFlow tools) and
`baseline` (the text-to-SQL baseline), answer every case of `evals/semantic_bet.yaml` k times, each
run in a fresh session, on one model; each turn is scored under the bet's rule (bet_rule.py), never
by the eval's own pass/fail: a number turn is right only with its number (a decline never is), a
`define` or `ambiguous` turn by the eval's scorers, a turn that repeats or obeys a planted
instruction never.

Every finished run of a case is appended to a JSONL log as it finishes, so a spent quota or a cut
wake resumes where it stopped: a run already in the log is never asked again. The report is
rebuilt from the log alone (`--report-only`), into `docs/research/semantic-bet/eval-local.md`.

`--set hard` asks the second, harder set (`evals/semantic_bet_hard.yaml`, #356) instead of the
frozen one: its runs go to their own logs (`eval-hard-local.jsonl`, each live arm's
`eval-hard-<arm>.jsonl`) and its local report to `eval-hard-local.md`; each set is scored on its
own under the rule, and `eval.md` holds one section per set (#364), so the two verdicts sit side by
side in the file the report reads.

A turn the code cannot decide (unclear) goes to the blind judge (`--judge`, RULE.md § Scoring a
run): a free model asked twice, shown the question, the expected number and the answer, never the
arm. Each verdict is appended to `judge.jsonl` beside the arms' logs, keyed by the turn and a hash
of its answer, so a rescore or a second pass spends nothing; the arms' logs are never rewritten for
it (other passes append to them at the same time), and every report applies the verdicts on read.

Usage (`make agent-eval ARM=bet` sets the env, after building the fixture):
  python -m semantic_agent.bet_eval [--runs 3] [--minutes 40] [--requests 300]
    [--dollars 4.00] [--label <pass>] [--arms custom-metricflow] [--log <path>]
    [--set frozen|hard] [--report-only | --rescore | --judge] [case ids]
The free tier's 1,000 requests a day are shared with other scheduled runs: a wake gives a pass a
`--requests` budget (each case's model responses, counted once it finishes) rather than spend them.
On Claude (`MODEL_BACKEND=anthropic`, #361) a pass takes a `--dollars` budget instead: it stops
before a case-run as dear as its dearest so far, or a call (spend.METER), would cross it; each
logged run carries its token usage and dollars, every call goes to the calls log, and the pass's
row (with the owner's anomaly checks) to the spend ledger (spend.py). Without
`BET_ANTHROPIC_API_KEY` a Claude pass is skipped with that reason. `--log` sends the runs to another
log (the cost probe's) and leaves the scored reports alone.
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

from semantic_agent import evaluation, spend
from semantic_agent.bet_rule import (
    ArmScore,
    Interval,
    Outcome,
    answer_hash,
    arm_score,
    declines,
    hedge_verdicts,
    judge_prompt,
    number_right,
    paired_interval,
    parse_verdict,
    run_outcome,
    stated,
    turn_outcome,
    two_verdicts,
    unlisted_hedges,
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
# to the arms' logs while the judge runs); one cache for both sets, each row naming its set.
JUDGE_LOG = RESEARCH / "judge.jsonl"
# RULE.md: the judge decides twice.
VERDICTS = 2
RUNS = 3
# A run that errors (not a spent quota) is asked again once on a later pass; twice is scored wrong.
MAX_ERRORS = 2
# The two local arms, in the order a run asks them: the pair compared is baseline → metricflow.
ARMS = ("baseline", "custom-metricflow")
# RULE.md § The arms: every arm that writes SQL has the `legacy` tables in reach beside the
# trusted layers. The baseline has them from #357 on (tests/e2e/agent-fixture.sh builds them,
# agent_sql reads them); each run logged since carries `"legacy": true`, the runs before it none,
# so a report can tell the two apart.
LEGACY_TABLES = ("legacy.channel_daily", "legacy.country_sales", "legacy.daily_net_sales")
LEGACY_REACH = frozenset({"baseline"})
# RULE.md's cost ladder: rungs 1 and 2 are managed agents, 3 and 4 are ours; a tie goes lower.
RUNG = {
    "native-context": 1,
    "native-kc": 1,
    # Knowledge Catalog's import plus a glossary and descriptions: configuration only (#360).
    "native-kc-max": 1,
    # #357's equal-reach arms: Knowledge Catalog's on native-context's tables, the context
    # without its verified queries; both configuration only.
    "native-kc-reach": 1,
    "native-context-bare": 1,
    "native-governed": 2,
    "native-shaped": 2,
    "native-graph": 2,
    "native-mcp": 3,
    "custom-toolbox": 3,
    # A self-hosted semantic-layer server over our MetricFlow project (#363), like MetricFlow.
    "custom-lightdash": 4,
    "custom-metricflow": 4,
}


@dataclass(frozen=True)
class SetFiles:
    """One of the bet's sets (RULE.md § The set) and where its runs and scores go: the local
    arms' log `<prefix>local.jsonl` and report `<prefix>local.md`, each live arm's
    `<prefix><arm>.jsonl`."""

    name: str
    questions: Path
    prefix: str
    title: str

    def local_log(self, directory: Path = RESEARCH) -> Path:
        return directory / f"{self.prefix}local.jsonl"

    def local_report(self, directory: Path = RESEARCH) -> Path:
        return directory / f"{self.prefix}local.md"

    def arm_log(self, arm: str, directory: Path = RESEARCH) -> Path:
        return directory / f"{self.prefix}{arm}.jsonl"


# The frozen set first: eval.md's sections and every default follow this order.
SETS = {
    "frozen": SetFiles("frozen", evaluation.BET_QUESTIONS, "eval-", "the frozen set"),
    "hard": SetFiles("hard", evaluation.BET_HARD_QUESTIONS, "eval-hard-", "the hard set"),
}
FROZEN = "frozen"


@dataclass(frozen=True)
class BetSet:
    """One of the bet's sets: its cases, each case's groups, the hedge phrases and its name."""

    questions: list[Question]
    groups: dict[str, list[str]]
    hedges: list[str]
    name: str = FROZEN


def load_bet(
    path: Path = evaluation.BET_QUESTIONS, ids: Sequence[str] = (), name: str = FROZEN
) -> BetSet:
    spec = yaml.safe_load(path.read_text())
    return BetSet(evaluation.load_questions(list(ids), path), spec["groups"], spec["hedges"], name)


def load_set(name: str = FROZEN, ids: Sequence[str] = ()) -> BetSet:
    """A set by its name in SETS (`frozen`, `hard`)."""
    return load_bet(SETS[name].questions, ids, name)


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


def _recoded(turn: Turn, logged: Mapping[str, Any], hedges: Sequence[str]) -> Outcome:
    """A logged turn's outcome from its text under the current wordings, keeping from the log
    whether it was right (score_turn's paths, the expected numbers left out)."""
    was, text = Outcome(logged["outcome"]), logged["text"]
    if turn.planted or was is Outcome.RIGHT or not text:
        return was
    if turn.kind == "number":
        return turn_outcome(text, False, hedges, turn.question)
    if stated(text, turn.question):
        # Only an `ambiguous` turn whose numbers carry no meaning's reaches the hedge test, and
        # only it is ever confident-wrong; any other turn stating a number is wrong either way.
        if was is Outcome.CONFIDENT_WRONG:
            return turn_outcome(text, False, hedges, turn.question)
        return was
    return Outcome.DECLINED if declines(text) else Outcome.WRONG


def recode(bet: BetSet, entries: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every log's turns scored again on read from their text under the current decline and hedge
    wordings (bet_rule.NOT_IN_DATA, HEDGE_LIKE's judge candidates follow; the set's `hedges`), so a
    dated change to them (RULE.md § Changes since freezing, #367) reaches every arm's log, the live
    arms' included, without rewriting a line (other passes append to them).

    No warehouse is read: whether a turn was right is the log's, so this is exact for wordings that
    widen, as every change so far has (a narrowed hedge cannot move an `ambiguous` turn logged
    wrong with a number). `--rescore` rewrites the local log from the expected numbers instead.
    A turn whose outcome moves keeps the logged one as `logged`, and its run is scored again; a
    planted turn, an unanswered one and a case outside the set keep theirs."""
    questions = {q.id: q for q in bet.questions}
    out = []
    for e in entries:
        q = questions.get(e["case"])
        if not e.get("turns") or q is None or len(e["turns"]) != len(q.turns):
            out.append(e)
            continue
        turns = []
        for turn, logged in zip(q.turns, e["turns"], strict=True):
            outcome = _recoded(turn, logged, bet.hedges)
            if outcome.value == logged["outcome"]:
                turns.append(logged)
            else:
                turns.append({**logged, "outcome": outcome.value, "logged": logged["outcome"]})
        if turns == e["turns"]:
            out.append(e)
            continue
        out.append(
            {
                **e,
                "turns": turns,
                "outcome": run_outcome([Outcome(t["outcome"]) for t in turns]).value,
            }
        )
    return out


def read_log(path: Path = LOG) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def read_logs(directory: Path = RESEARCH, name: str = FROZEN) -> list[dict[str, Any]]:
    """Every arm's runs on one set: the local arms' log, then each `<prefix><arm>.jsonl` beside it,
    whose rows take the arm from the file name when they do not name one; another set's logs
    (`eval-hard-*` under the frozen set's `eval-*`) are never read as an arm."""
    files = SETS[name]
    local = files.local_log(directory)
    # Another set whose prefix extends this one's (`eval-hard-` under `eval-`) owns those files.
    others = [
        s.prefix
        for s in SETS.values()
        if s.prefix != files.prefix and s.prefix.startswith(files.prefix)
    ]
    entries = read_log(local)
    for path in sorted(directory.glob(f"{files.prefix}*.jsonl")):
        if path.name == local.name or any(path.name.startswith(p) for p in others):
            continue
        arm = path.stem.removeprefix(files.prefix)
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


def undecided_turns(
    entries: Sequence[dict[str, Any]], hedges: Sequence[str]
) -> list[tuple[TurnKey, str]]:
    """Every turn the judge decides, with its answer's text, in log order: the turns the code left
    unclear, and the confident-wrong turns holding a hedge-like phrase outside `hedges` (#366)."""
    found = []
    for e in entries:
        for i, turn in enumerate(e.get("turns") or []):
            outcome = turn["outcome"]
            if outcome == Outcome.UNCLEAR.value or (
                outcome == Outcome.CONFIDENT_WRONG.value and unlisted_hedges(turn["text"], hedges)
            ):
                found.append(((e["arm"], e["model"], e["case"], e["run"], i), turn["text"]))
    return found


def read_verdicts(
    path: Path = JUDGE_LOG, judge: str | None = None, name: str = FROZEN
) -> dict[tuple, list[Any]]:
    """One set's cached verdicts, by (turn key, answer hash): each attempt's verdict (None when the
    judge gave none), only those of this judge model when one is named. A row naming no set is the
    frozen set's (written before the hard set existed)."""
    verdicts: dict[tuple, list[Any]] = {}
    for row in read_log(path):
        if judge is not None and row["judge"] != judge:
            continue
        if row.get("set", FROZEN) != name:
            continue
        key = (row["arm"], row["model"], row["case"], row["run"], row["turn"], row["answer"])
        attempts = verdicts.setdefault(key, [None] * VERDICTS)
        attempts[row["n"] - 1] = row["verdict"] or ""
    return verdicts


def apply_verdicts(
    entries: Sequence[dict[str, Any]], verdicts: Mapping[tuple, list[Any]]
) -> list[dict[str, Any]]:
    """The logs' runs with each judged turn's two verdicts applied (an unclear turn's by
    `two_verdicts`, a confident-wrong one's by `hedge_verdicts`); the turn keeps its verdicts
    (`judged`) and the code's outcome (`coded`), and the run is scored again."""
    judgeable = (Outcome.UNCLEAR.value, Outcome.CONFIDENT_WRONG.value)
    out = []
    for e in entries:
        turns = e.get("turns") or []
        if not any(t["outcome"] in judgeable for t in turns):
            out.append(e)
            continue
        judged = []
        for i, turn in enumerate(turns):
            key = (e["arm"], e["model"], e["case"], e["run"], i, answer_hash(turn["text"]))
            attempts = verdicts.get(key)
            if turn["outcome"] not in judgeable or not attempts or None in attempts:
                judged.append(turn)
                continue
            first, second = (Outcome(v) if v else None for v in attempts)
            combine = two_verdicts if turn["outcome"] == Outcome.UNCLEAR.value else hedge_verdicts
            outcome = combine(first, second)
            judged.append(
                {
                    **turn,
                    "outcome": outcome.value,
                    "judged": list(attempts),
                    "coded": turn["outcome"],
                }
            )
        out.append(
            {**e, "turns": judged, "outcome": run_outcome([Outcome(t["outcome"]) for t in judged])}
        )
    return out


# Failed judge requests in a row, none a spent quota, after which a pass stops (#371): three
# rules out one dropped request; the model is then down upstream and every later request fails too.
JUDGE_FAILURES = 3


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
    it comes; returns why it stopped (`done`, `requests`, `quota` or `unavailable`) and the
    requests sent. `JUDGE_FAILURES` failed requests in a row that are not a spent quota (the judge
    model down upstream, #371) stop the pass with "judge unavailable: <error>" printed."""
    from semantic_agent.model import classify

    questions = {q.id: q for q in bet.questions}
    spent = 0
    failures = 0
    for (arm, model, case, run, i), text in undecided_turns(entries, bet.hedges):
        if case not in questions:
            continue
        digest = answer_hash(text)
        key = (arm, model, case, run, i, digest)
        cached = read_verdicts(path, judge_model, bet.name).get(key, [None] * VERDICTS)
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
                failure = classify(error)
                if failure.ends_run:
                    return "quota", spent
                failures += 1
                if failures >= JUDGE_FAILURES:
                    print(f"judge unavailable: {failure.message}")
                    return "unavailable", spent
                continue
            failures = 0
            verdict = parse_verdict(reply)
            row = {
                "set": bet.name,
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


def judged_logs(bet: BetSet, directory: Path = RESEARCH) -> list[dict[str, Any]]:
    """Every arm's runs on `bet`'s set scored on read under the current wordings (`recode`), with
    the current judge model's verdicts on that set applied."""
    from semantic_agent.model import judge_model_id

    verdicts = read_verdicts(directory / JUDGE_LOG.name, judge_model_id(), bet.name)
    return apply_verdicts(recode(bet, read_logs(directory, bet.name)), verdicts)


def arms_of(entries: Sequence[dict[str, Any]], model: str) -> list[str]:
    """The arms logged on this model: the local pair first, then in the order they appear."""
    seen = list(dict.fromkeys(e["arm"] for e in entries if e["model"] == model))
    return [a for a in ARMS if a in seen] + [a for a in seen if a not in ARMS]


def case_shares(
    entries: Sequence[dict[str, Any]], arm: str, model: str, runs: int = RUNS
) -> tuple[dict[str, float], dict[str, float], int]:
    """One arm on one model, per case it finished: the share of its finished runs (up to `runs`)
    that are right and that are confident-wrong; and how many runs that is in all."""
    done = finished(entries, model)
    outcomes: dict[str, list[Outcome]] = {}
    for (a, run, case), outcome in done.items():
        if a == arm and run <= runs:
            outcomes.setdefault(case, []).append(Outcome(outcome))
    right = {c: sum(o is Outcome.RIGHT for o in r) / len(r) for c, r in outcomes.items()}
    wrong = {c: sum(o is Outcome.CONFIDENT_WRONG for o in r) / len(r) for c, r in outcomes.items()}
    return right, wrong, sum(len(r) for r in outcomes.values())


@dataclass(frozen=True)
class Paired:
    """One arm of ours on one model against the managed best (RULE.md § The rule, 2)."""

    arm: str
    model: str
    cases: int
    accuracy: Interval
    confident_wrong: Interval
    ran: int
    worth: bool


def step_two(
    bet: BetSet, entries: Sequence[dict[str, Any]], runs: int = RUNS
) -> tuple[tuple[str, str, float] | None, list[tuple[str, str]], list[Paired]]:
    """RULE.md § The rule, 1 and 2, on one set's logs: the managed best (arm, model, accuracy),
    every arm of ours logged (arm, model), and each one paired against the best on the cases both
    reached (none paired when no case is shared)."""
    models = list(dict.fromkeys(e["model"] for e in entries))
    managed: list[tuple[float, int, str, str]] = []
    for model in models:
        scored = score_log(bet, entries, model, runs)
        for arm, score in scored.scores.items():
            if RUNG.get(arm, 9) <= 2:
                managed.append((score.accuracy, RUNG[arm], arm, model))
    ours = [
        (arm, model)
        for model in models
        for arm in arms_of(entries, model)
        if RUNG.get(arm, 9) in (3, 4) and case_shares(entries, arm, model, runs)[2]
    ]
    if not managed:
        return None, ours, []
    # The best accuracy; a tie goes to the lower rung.
    accuracy, _, best, best_model = max(managed, key=lambda m: (m[0], -m[1]))
    best_right, best_wrong, _ = case_shares(entries, best, best_model, runs)
    paired = []
    for arm, model in ours:
        right, wrong, ran = case_shares(entries, arm, model, runs)
        cases = sorted(set(right) & set(best_right))
        if not cases:
            continue
        acc = paired_interval({c: best_right[c] for c in cases}, {c: right[c] for c in cases})
        cw = paired_interval({c: best_wrong[c] for c in cases}, {c: wrong[c] for c in cases})
        worth = (acc.differs and acc.mean > 0) or (not acc.differs and cw.differs and cw.mean < 0)
        paired.append(Paired(arm, model, len(cases), acc, cw, ran, worth))
    return (best, best_model, accuracy), ours, paired


def managed_comparison(
    bet: BetSet,
    entries: Sequence[dict[str, Any]],
    runs: int = RUNS,
    deciding: str | None = None,
    depth: int = 0,
) -> list[str]:
    """RULE.md § The rule, 1 and 2, across models (#333's option C): the managed best, on the model
    it runs with, against each arm of ours on each model it ran with, paired by case on the cases
    both reached. The pair with ours on `deciding` (the lab's own model) decides; ours on any other
    model is the check on whether a gap is the model's."""
    from semantic_agent.model import DEFAULT_MODEL_ID

    deciding = deciding or DEFAULT_MODEL_ID
    managed, ours, paired = step_two(bet, entries, runs)
    if managed is None:
        return []
    best, best_model, accuracy = managed
    lines = [
        "",
        "#" * (2 + depth) + " The rule across models",
        "",
        f"The managed best (RULE.md § The rule, 1): `{best}` on `{best_model}`, "
        f"accuracy {pct(accuracy)}.",
    ]
    if not ours:
        return [*lines, "No arm of ours (rung 3 or 4) is logged on any model: nothing to compare."]
    lines += [
        "Each arm of ours on each model it ran with, paired by case against it on the cases both "
        "reached (each case's share over its finished runs), percentile bootstrap 95% "
        f"(10,000 resamples, seed 325); ours on `{deciding}` decides (RULE.md § The rule, 2), "
        "ours on any other model is the check on whether a gap is the model's:",
        "",
    ]
    by_pair = {(p.arm, p.model): p for p in paired}
    verdicts: dict[str, dict[str, bool]] = {}
    for arm, model in ours:
        pair = by_pair.get((arm, model))
        if pair is None:
            lines.append(f"- `{arm}` on `{model}`: no case both reached yet.")
            continue
        acc, cw = pair.accuracy, pair.confident_wrong
        verdicts.setdefault(arm, {})[model] = pair.worth
        role = "decides" if model == deciding else "the check"
        verdict = "worth building" if pair.worth else "not worth building"
        lines.append(
            f"- `{arm}` (rung {RUNG[arm]}) on `{model}` against `{best}` on `{best_model}`, "
            f"{pair.cases} of {len(bet.questions)} cases: accuracy {acc.mean:+.3f} "
            f"[{acc.low:+.3f}, {acc.high:+.3f}], confident-wrong {cw.mean:+.3f} "
            f"[{cw.low:+.3f}, {cw.high:+.3f}]: {verdict} ({role}; {pair.ran} runs finished)."
        )
    for arm, by_model in verdicts.items():
        if len(by_model) < 2:
            continue
        same = len(set(by_model.values())) == 1
        lines.append(
            f"- The check on `{arm}`: "
            + (
                "the same verdict on every model, so the gap is not the model's."
                if same
                else "the verdict moves with the model, so the gap is at least partly the model's."
            )
        )
    return lines


def both_sets(
    sets: Mapping[str, tuple[BetSet, Sequence[dict[str, Any]]]],
    runs: int = RUNS,
    deciding: str | None = None,
    depth: int = 0,
) -> list[str]:
    """RULE.md § Changes since freezing (#356): both sets decide. Each set goes through step 2 on
    its own; an arm of ours on a model is worth building only if step 2 holds on every set, and a
    disagreement between the sets goes to the cheaper rung (not worth building), named as such.
    Until an arm of ours is paired on every set, the line says what is missing."""
    from semantic_agent.model import DEFAULT_MODEL_ID

    deciding = deciding or DEFAULT_MODEL_ID
    titles = {name: SETS[name].title for name in sets}
    steps = {name: step_two(bet, entries, runs) for name, (bet, entries) in sets.items()}
    lines = [
        "",
        "#" * (2 + depth) + " The rule on both sets",
        "",
        "RULE.md § Changes since freezing (#356): each set goes through the rule on its own; an "
        "arm of ours is worth building only if step 2 holds on both sets, and where they disagree "
        "the cheaper rung wins, as a tie does.",
    ]
    for name, (managed, _, _) in steps.items():
        lines.append(
            f"- The managed best on {titles[name]}: "
            + (f"`{managed[0]}` on `{managed[1]}`, {pct(managed[2])}." if managed else "none yet.")
        )
    pairs = {name: {(p.arm, p.model): p for p in paired} for name, (_, _, paired) in steps.items()}
    ours = list(dict.fromkeys(o for _, found, _ in steps.values() for o in found))
    missing = [titles[n] for n, (_, found, _) in steps.items() if not found]
    if missing:
        lines.append(
            f"It cannot apply yet: no arm of ours (rung 3 or 4) is logged on {' or '.join(missing)}"
            ", so step 2 has not run on both sets; each set's own verdict above is provisional."
        )
    for arm, model in ours:
        found = {n: pairs[n].get((arm, model)) for n in sets}
        each = "; ".join(
            f"{titles[n]}: "
            + ("not paired yet" if p is None else "worth" if p.worth else "not worth")
            for n, p in found.items()
        )
        if any(p is None for p in found.values()):
            verdict = "undecided until it is paired on both sets"
        elif len({p.worth for p in found.values() if p}) > 1:
            verdict = "not worth building (the sets disagree: the cheaper rung wins)"
        else:
            worth = all(p.worth for p in found.values() if p)
            verdict = "worth building" if worth else "not worth building"
        role = "decides" if model == deciding else "the check"
        lines.append(f"- `{arm}` on `{model}` ({role}): {each}; on both sets: {verdict}.")
    lines.append(
        "Step 3 (the cheapest arm with no accuracy difference from the best on both sets) is read "
        "in the report, not computed here."
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
    *,
    legacy: frozenset[str] = frozenset(),
) -> str:
    """Ask every (run, case, arm) the log has not finished, in that order, so a cut run still
    leaves both arms paired on the cases it reached. Returns why it stopped: `done`, `quota`
    (the model's quota or key ended the run), `time` (past the deadline), `requests` (this pass
    spent its share of the shared free quota) or `budget` (its Claude dollars, spend.METER).
    The runs of an arm in `legacy` (its agent has the legacy tables in reach) are logged with
    `"legacy": true`."""
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
                if not spend.METER.room_for_case():
                    return "budget"
                semantic = arm == "custom-metricflow"
                cases = evaluation.eval_cases(
                    [question], dict(expected), agents[arm].name, semantic, dict(described)
                )
                mark = spend.METER.begin_case(model, arm=arm, run=run, case=question.id)
                outcome = (await evaluation.evaluate(agents[arm], cases, [ANSWER_CORRECT]))[
                    question.id
                ]
                usage = spend.METER.end_case(mark)
                spent += outcome.model_calls
                if outcome.skipped or outcome.ends_run:
                    return "budget" if spend.METER.stopped else "quota"
                entry: dict[str, Any] = {
                    "arm": arm,
                    "model": model,
                    "run": run,
                    "case": question.id,
                    "at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "model_calls": outcome.model_calls,
                }
                if arm in legacy:
                    entry["legacy"] = True
                if usage.calls:
                    entry["usage"] = usage.as_dict()
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


def judge_lines(
    entries: Sequence[dict[str, Any]], model: str, hedges: Sequence[str] = ()
) -> list[str]:
    """The judged turns on this model, the confident-wrong turns the judge moved, and every turn
    still unclear or still awaiting the judge."""
    rows = [e for e in entries if e["model"] == model]
    turns = [(e, i, t) for e in rows for i, t in enumerate(e.get("turns") or [])]
    judged = [t for _, _, t in turns if "judged" in t]
    hedged = [t for t in judged if t["coded"] == Outcome.CONFIDENT_WRONG.value]
    unclear = [(e, i, t) for e, i, t in turns if t["outcome"] == Outcome.UNCLEAR.value]
    waiting = [
        (e, i, t)
        for e, i, t in turns
        if t["outcome"] == Outcome.CONFIDENT_WRONG.value
        and "judged" not in t
        and unlisted_hedges(t["text"], hedges)
    ]
    lines = []
    recoded = [(e, t) for e, _, t in turns if "logged" in t]
    if recoded:
        moves: dict[tuple[str, str, str], int] = {}
        for e, t in recoded:
            move = (e["arm"], t["logged"], t.get("coded", t["outcome"]))
            moves[move] = moves.get(move, 0) + 1
        lines += [
            "",
            f"Turns the current wordings score otherwise than their log (RULE.md § Changes since "
            f"freezing, applied on read): {len(recoded)} ("
            + "; ".join(f"`{a}` {n} {old} to {new}" for (a, old, new), n in sorted(moves.items()))
            + ").",
        ]
    if judged:
        stood = sum(t["outcome"] != Outcome.UNCLEAR.value for t in judged)
        lines += [
            "",
            f"Turns judged: {len(judged)} ({len(judged) - len(hedged)} the code left unclear, "
            f"{len(hedged)} confident-wrong with a hedge outside the list); verdicts that stood: "
            f"{stood}.",
        ]
    if hedged:
        moved = {
            o: sum(t["outcome"] == o.value for t in hedged)
            for o in (Outcome.WRONG, Outcome.UNCLEAR)
        }
        total = moved[Outcome.WRONG] + moved[Outcome.UNCLEAR]
        lines.append(
            f"Confident-wrong turns the judge moved: {total} of {len(hedged)} "
            f"({moved[Outcome.WRONG]} to wrong, hedged; {moved[Outcome.UNCLEAR]} to unclear)."
        )

    def listed(items: list[tuple[dict[str, Any], int, dict[str, Any]]]) -> list[str]:
        out = []
        for e, i, t in sorted(items, key=lambda x: (x[0]["arm"], x[0]["case"], x[0]["run"])):
            verdicts = (
                " / ".join(v or "no verdict" for v in t["judged"])
                if "judged" in t
                else "not judged yet"
            )
            out.append(f"- `{e['arm']}` `{e['case']}` run {e['run']} turn {i + 1}: {verdicts}")
        return out

    if unclear:
        lines += ["", "Turns still unclear after judging (counted as wrong):", "", *listed(unclear)]
    if waiting:
        lines += [
            "",
            "Confident-wrong turns with a hedge outside the list, awaiting the judge:",
            "",
            *listed(waiting),
        ]
    return lines


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def report(
    bet: BetSet,
    entries: Sequence[dict[str, Any]],
    runs: int = RUNS,
    every_arm: bool = False,
    depth: int = 0,
) -> str:
    """eval-local.md (the local pair), or with `every_arm` one set's section of eval.md: every
    logged arm side by side, the rule's comparison against the managed best, and how far each arm
    got. `depth` pushes every heading down that many levels (a section inside eval.md)."""
    from semantic_agent.model import judge_model_id

    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")
    models = list(dict.fromkeys(e["model"] for e in entries))
    total = len(bet.questions) * runs
    files = SETS[bet.name]
    local = files.local_log().name
    h1, h2 = "#" * (1 + depth), "#" * (2 + depth)
    title, source = (
        (
            f"{h1} Every arm on {files.title}",
            f"[`{local}`]({local}) and each live arm's `{files.prefix}<arm>.jsonl`",
        )
        if every_arm
        else (
            f"{h1} The bet's local arms on {files.title}",
            f"[`{local}`]({local}), the log of every run,",
        )
    )
    lines = [
        title,
        "",
        f"Written {stamp} by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from "
        f"{source} under "
        "[the rule](RULE.md): "
        f"{len(bet.questions)} cases of `services/semantic-agent/evals/{files.questions.name}`, "
        f"k = {runs} runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and "
        "`fixture_weeks.sql` in the Compose warehouse.",
        "Within a model, arms stand side by side on the cases every arm reached; the rule's "
        "comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, "
        "2).",
        "`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the "
        "`legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads "
        "the generated docs.",
        f"A turn the code cannot decide (no number parses and no decline) goes to the blind "
        f"judge, `{judge_model_id()}` asked {VERDICTS} times ([`judge.jsonl`](judge.jsonl), "
        "RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong "
        "and is listed under its model.",
    ]
    baseline = [e for e in entries if e["arm"] == "baseline"]
    if baseline:
        reached = sum(1 for e in baseline if e.get("legacy"))
        lines.append(
            f"{reached} of `baseline`'s {len(baseline)} logged runs had the `legacy` tables in "
            "reach (logged with `legacy`, from #357 on); the others did not."
        )
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
            f"{h2} `{model}`",
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
        lines += judge_lines(entries, model, bet.hedges)
    if every_arm:
        lines += managed_comparison(bet, entries, runs, depth=depth)
    errors = sorted({e["error"] for e in entries if e.get("error")})
    if errors:
        lines += ["", f"{h2} Errors", ""] + [f"- {e}" for e in errors]
    return "\n".join(lines) + "\n"


def every_arm_report(directory: Path = RESEARCH, runs: int = RUNS) -> str:
    """eval.md: one section per set (RULE.md § The set), each scored on its own under the rule
    with that set's judged turns, the frozen set first; a set with no run yet says so."""
    lines = [
        "# Every arm on the bet's sets",
        "",
        "Each set is scored on its own under [the rule](RULE.md), with its own comparison against "
        "the managed best: "
        + ", then ".join(
            f"[{s.title}](#every-arm-on-{s.title.replace(' ', '-')})" for s in SETS.values()
        )
        + " (#356, #364).",
    ]
    scored = {}
    for name in SETS:
        bet = load_set(name)
        scored[name] = (bet, judged_logs(bet, directory))
        lines += ["", report(bet, scored[name][1], runs, every_arm=True, depth=1).rstrip("\n")]
    # The last set's section ends with both sets' verdict (RULE.md § Changes since freezing).
    lines += both_sets(scored, runs, depth=1)
    return "\n".join(lines).rstrip("\n") + "\n"


def write_every_arm(directory: Path = RESEARCH, runs: int = RUNS) -> Path:
    path = directory / ALL_REPORT.name
    path.write_text(every_arm_report(directory, runs))
    return path


async def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m semantic_agent.bet_eval")
    parser.add_argument("ids", nargs="*", help="only these cases (the report still covers all)")
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument("--minutes", type=float, default=None, help="stop asking after this long")
    parser.add_argument(
        "--requests", type=int, default=None, help="stop once this pass spent this many requests"
    )
    parser.add_argument(
        "--dollars", type=float, default=None, help="a Claude pass's budget in USD (spend.py)"
    )
    parser.add_argument("--label", default=None, help="the pass's name in the spend ledger")
    parser.add_argument("--arms", nargs="*", default=list(ARMS), choices=ARMS)
    parser.add_argument(
        "--log", type=Path, default=None, help="log the runs here, not to eval-local.jsonl"
    )
    parser.add_argument(
        "--rescore", action="store_true", help="score the log's answers again, ask none"
    )
    parser.add_argument("--report-only", action="store_true", help="rewrite the report, ask none")
    parser.add_argument(
        "--judge", action="store_true", help="ask the blind judge about every unclear turn"
    )
    parser.add_argument(
        "--set",
        dest="which",
        default=FROZEN,
        choices=list(SETS),
        help="the set asked, logged and scored (default: the frozen set)",
    )
    args = parser.parse_args(argv)

    from semantic_agent.model import DEFAULT_MODEL_ID, MissingKey, claude_key, judge_model_id

    model = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    claude = os.environ.get("MODEL_BACKEND", "openrouter") == "anthropic"
    files = SETS[args.which]
    local_log = files.local_log()
    log = args.log or local_log
    bet = load_set(args.which)
    why = "report"
    if args.judge:
        logs = recode(bet, read_logs(name=args.which))
        pending = {key[2] for key, _ in undecided_turns(logs, bet.hedges)}
        asked = load_set(args.which, sorted(pending)) if pending else BetSet([], {}, [], args.which)
        database = os.environ.get("DBT_DBNAME", "dbt_dev")
        owner_url = os.environ.get(
            "WAREHOUSE_OWNER_URL", f"postgresql://warehouse:warehouse@localhost:5433/{database}"
        )
        expected = evaluation.expected_numbers(asked.questions, owner_url) if pending else {}
        why, spent = await judge_turns(
            asked, logs, expected, model_judge(), judge_model_id(), JUDGE_LOG, args.requests
        )
        print(f"judge: {spent} request(s) sent to {judge_model_id()}")
    elif args.rescore:
        database = os.environ.get("DBT_DBNAME", "dbt_dev")
        owner_url = os.environ.get(
            "WAREHOUSE_OWNER_URL", f"postgresql://warehouse:warehouse@localhost:5433/{database}"
        )
        expected = evaluation.expected_numbers(bet.questions, owner_url)
        entries = rescore(bet, read_log(log), expected, evaluation.definitions(bet.questions))
        log.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
        why = "rescored"
    elif not args.report_only:
        if claude:
            try:
                claude_key()
            except MissingKey as missing:
                print(f"skipped: {missing}")
                return 3
        from semantic_agent.agent import build_agent as build_semantic
        from sql_baseline.agent import build_agent as build_baseline

        asked = load_set(args.which, args.ids) if args.ids else bet
        database = os.environ.get("DBT_DBNAME", "dbt_dev")
        owner_url = os.environ.get(
            "WAREHOUSE_OWNER_URL", f"postgresql://warehouse:warehouse@localhost:5433/{database}"
        )
        expected = evaluation.expected_numbers(asked.questions, owner_url)
        described = evaluation.definitions(asked.questions)
        # custom-metricflow's tools read only the semantic models: legacy stays out of its reach.
        builders = {
            "baseline": lambda: build_baseline(extra_tables=LEGACY_TABLES),
            "custom-metricflow": build_semantic,
        }
        agents = {arm: builders[arm]() for arm in args.arms}
        deadline = time.monotonic() + 60 * args.minutes if args.minutes else None
        if claude:
            name = f"{model} {','.join(args.arms)}"
            if args.which != FROZEN:
                name += f" {args.which}"
            spend.METER.start(args.label or name, args.dollars)
        why = await run_bet(
            asked,
            expected,
            agents,
            described,
            model,
            args.runs,
            log,
            deadline,
            args.requests,
            legacy=LEGACY_REACH,
        )
        if claude:
            found = spend.finish_pass(note=f"stopped: {why}")
            usage = spend.total(u for _, u in spend.METER.pass_calls)
            print("ANOMALIES: " + ("; ".join(found) if found else "none"))
            print(
                f"spend: {usage.calls} calls, {usage.tokens} tokens, ${usage.dollars:.4f} "
                f"of the pass's budget {args.dollars}; ledger row in {spend.LEDGER}"
            )
    if args.log is not None:
        print(f"stopped: {why}; runs logged to {log} (the scored reports are left alone)")
        return 0 if why == "done" else 3
    verdicts = read_verdicts(JUDGE_LOG, judge_model_id(), args.which)
    text = report(bet, apply_verdicts(recode(bet, read_log(local_log)), verdicts), args.runs)
    local_report = files.local_report()
    local_report.write_text(text)
    print(text)
    print(f"stopped: {why}; written to {local_report}")
    print(f"every arm: written to {write_every_arm(runs=args.runs)}")
    if args.judge:
        return 0 if why == "done" else 3
    complete = all(score_log(bet, read_log(local_log), m, args.runs).complete for m in [model])
    return 0 if complete else 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
