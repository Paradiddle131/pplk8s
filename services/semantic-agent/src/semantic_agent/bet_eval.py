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

`--set hard-v2` asks the hard set's version 2 (`evals/semantic_bet_hard_v2.yaml`, #377, RULE.md §
Set versions), which supersedes `hard`: its logs are `eval-hard-v2-*`, v1's runs of its unchanged
cases are copied into them by `semantic_agent.bet_carry` (so a pass asks only its new cases), and
its section in `eval.md` is descriptive until the owner's go: the verdict on both sets reads the
sets in DECIDING (#380, #381).

A turn the code cannot decide (unclear) goes to the blind judge (`--judge`, RULE.md § Scoring a
run): a free model asked twice, shown the question, the expected number and the answer, never the
arm. Each verdict is appended to `judge.jsonl` beside the arms' logs, keyed by the turn and a hash
of its answer, so a rescore or a second pass spends nothing; the arms' logs are never rewritten for
it (other passes append to them at the same time), and every report applies the verdicts on read.

Usage (`make agent-eval ARM=bet` sets the env, after building the fixture):
  python -m semantic_agent.bet_eval [--runs 3] [--minutes 40] [--requests 300]
    [--dollars 4.00] [--label <pass>] [--arms custom-metricflow] [--log <path>]
    [--set frozen|hard|hard-v2] [--report-only | --rescore | --judge] [case ids]
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
import hashlib
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
from google.adk.evaluation.eval_case import Invocation, get_all_tool_calls, get_all_tool_responses
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from semantic_agent import bet_tools, evaluation, spend
from semantic_agent.bet_rule import (
    ArmScore,
    Interval,
    Outcome,
    answer_hash,
    arm_score,
    at_risk,
    declines,
    define_prompt,
    first_figure_is_expected,
    hedge_verdicts,
    judge_prompt,
    number_right,
    paired_interval,
    parse_verdict,
    run_outcome,
    stated,
    stated_reading,
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
ARMS = ("baseline", "custom-metricflow", "custom-hybrid", "custom-metricflow-compute")
# What a pass asks when --arms is not given: the pair the local log has always held.
DEFAULT_ARMS = ("baseline", "custom-metricflow")
# RULE.md § The arms: every arm that writes SQL has the `legacy` tables in reach beside the
# trusted layers. The baseline has them from #357 on (tests/e2e/agent-fixture.sh builds them,
# agent_sql reads them); each run logged since carries `"legacy": true`, the runs before it none,
# so a report can tell the two apart.
LEGACY_TABLES = ("legacy.channel_daily", "legacy.country_sales", "legacy.daily_net_sales")
LEGACY_REACH = frozenset({"baseline", "custom-hybrid"})
# RULE.md § The arms, the reach policy (2026-11-09, #445): every SQL-writing setup reaches the
# row-level data Google's agents and `native-mcp` reach, so `baseline` and the hybrid's fallback
# read `silver` (column by column as `agent_metrics` does, personal columns refused) and the fiscal
# calendar (`semantic.time_spine`, #436), granted in the fixture (tests/e2e/agent-fixture.sh).
# Their runs logged since carry `"reach": REACH`; the runs before it carry none.
SQL_REACH_SCHEMAS = ("silver", "semantic")
REACH = "silver"


def reach_tables(url: str | None = None) -> tuple[str, ...]:
    """The `silver` and `semantic` tables `agent_sql` may read in the fixture, as `schema.table`
    (information_schema shows a role only what it holds a privilege on)."""
    import psycopg

    from sql_baseline.agent import _url

    with psycopg.connect(url or _url()) as conn:
        rows = conn.execute(
            "select table_schema || '.' || table_name from information_schema.tables "
            "where table_schema = any(%s) order by 1",
            [list(SQL_REACH_SCHEMAS)],
        ).fetchall()
    return tuple(r[0] for r in rows)


# RULE.md's cost ladder: rungs 1 and 2 are managed agents, 3 and 4 are ours; a tie goes lower.
RUNG = {
    "native-context": 1,
    "native-kc": 1,
    # Knowledge Catalog's import plus a glossary and descriptions: configuration only (#360).
    "native-kc-max": 1,
    # The floor: the tables only, no catalog links, descriptions or authored context (#372).
    "native-bare": 1,
    # #357's equal-reach arms: Knowledge Catalog's on native-context's tables, the context
    # without its verified queries; both configuration only.
    "native-kc-reach": 1,
    "native-context-bare": 1,
    "native-context-python": 1,
    "native-governed": 2,
    "native-shaped": 2,
    "native-graph": 2,
    "native-mcp": 3,
    "custom-toolbox": 3,
    # A self-hosted semantic-layer server over our MetricFlow project (#363), like MetricFlow.
    "custom-lightdash": 4,
    "custom-metricflow": 4,
    # MetricFlow first, a read-only SQL fallback for what no metric covers (#373).
    "custom-hybrid": 4,
    # MetricFlow with the arithmetic over metric results Google's governed agent does in SQL (#400).
    "custom-metricflow-compute": 4,
    # The same MetricFlow tools through a Claude Code subagent on the subscription (#374): another
    # agent harness, not the rule's arm; the report names it apart.
    "cc-metricflow": 4,
    # custom-metricflow-compute's instruction from headless Claude Code (#400), descriptive.
    "cc-metricflow-compute": 4,
    # Google's MCP tools through a headless Claude Code run (#387, #388), mirroring native-mcp:
    # another harness, descriptive like cc-metricflow.
    "cc-native-mcp": 3,
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
    "hard-v2": SetFiles(
        "hard-v2", evaluation.BET_HARD_V2_QUESTIONS, "eval-hard-v2-", "the hard set v2"
    ),
}
FROZEN = "frozen"
# The sets the rule's verdict reads (RULE.md § Changes since freezing, § Set versions): `hard-v2`
# takes `hard`'s place only after the owner's go on #380's comparison (#381); until then its section
# in eval.md is descriptive.
DECIDING = ("frozen", "hard")


@dataclass(frozen=True)
class BetSet:
    """One of the bet's sets: its cases, each case's groups, the hedge phrases and its name."""

    questions: list[Question]
    groups: dict[str, list[str]]
    hedges: list[str]
    name: str = FROZEN
    # The cases a set version adds to the set it supersedes (its `new` list, RULE.md § Set
    # versions); empty for a first version.
    new: tuple[str, ...] = ()


def load_bet(
    path: Path = evaluation.BET_QUESTIONS,
    ids: Sequence[str] = (),
    name: str = FROZEN,
    overlay: Path = RESEARCH,
) -> BetSet:
    spec = yaml.safe_load(path.read_text())
    # A retired case (RULE.md § Retiring a defective case) is no longer part of any set as scored.
    retired, _ = read_overlay(overlay)
    questions = [q for q in evaluation.load_questions(list(ids), path) if q.id not in retired]
    groups = {c: g for c, g in spec["groups"].items() if c not in retired}
    groups.update({c: g for c, g in read_labels(overlay, name).items() if c in groups})
    new = tuple(c for c in spec.get("new") or () if c not in retired)
    return BetSet(questions, groups, spec["hedges"], name, new)


def yaml_ids(path: Path) -> set[str]:
    return {case["id"] for case in yaml.safe_load(path.read_text())["questions"]}


def load_set(name: str = FROZEN, ids: Sequence[str] = (), overlay: Path = RESEARCH) -> BetSet:
    """A set by its name in SETS (`frozen`, `hard`, `hard-v2`), as scored: without the cases the
    overlay beside the logs (`overlay`) retires, with its corrected labels."""
    return load_bet(SETS[name].questions, ids, name, overlay)


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
        right = number_right(text, numbers)
        # #382: a small or common expected number stands by the code only as the answer's own
        # first figure; otherwise the blind judge decides whether the answer's answer is it.
        # An answer that also declines ("hourly data is not available ... 2 checkouts") may carry
        # the number as a count of something else: the judge's too.
        risky = right and at_risk(numbers, turn.question)
        if risky and (declines(text) or not first_figure_is_expected(text, numbers, turn.question)):
            return Outcome.UNCLEAR
        return turn_outcome(text, right, hedges, turn.question)
    if turn.kind == "define":
        right = all(_words(described[name]) in _words(text) for name in turn.define)
        # #382: a definition put in the answer's own words is the judge's to read, not wrong.
        if not right and text.strip() and not declines(text):
            return Outcome.UNCLEAR
    else:
        # #435: on a relative-date ambiguity, one reading's figure with that reading's dates.
        right = asks_or_gives_each(text, numbers) or stated_reading(text, turn.question, numbers)
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


def recode(
    bet: BetSet,
    entries: Sequence[dict[str, Any]],
    expected: Mapping[str, Expected] | None = None,
    described: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
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
        known = expected.get(e["case"]) if expected is not None else None
        for i, (turn, logged) in enumerate(zip(q.turns, e["turns"], strict=True)):
            # With the cached expected numbers (#382), every turn but a planted or unanswered one
            # is scored again in full, so a change to how numbers are read reaches every log.
            if known is not None and not turn.planted and logged.get("text"):
                outcome = score_turn(turn, known[i], logged["text"], bet.hedges, described or {})
            else:
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


# RULE.md § Retiring a defective case (#382): an overlay beside the logs, never an edit of them.
# Each row is a retired case ({"kind": "case", "case": ...}: every run of it, in every set, leaves
# the scores) or a redacted run ({"kind": "run", "arm", "model", "case", "run", "at"}: that logged
# row only, so the runner asks the run again and a later run of the same key is kept); each with
# its `reason`, `evidence`, `issue` and the date. Rows are appended; a row with `"undo": true`
# reverses an earlier one.
OVERLAY = "redacted.jsonl"


def run_key(row: Mapping[str, Any]) -> tuple:
    """A logged run as the overlay names it; `at` tells a rerun of the same run number apart."""
    return (row.get("arm"), row.get("model"), row.get("case"), row.get("run"), row.get("at"))


def read_overlay(directory: Path = RESEARCH) -> tuple[set[str], set[tuple]]:
    """The retired cases and the redacted runs in force (an `undo` row lifts an earlier one)."""
    cases: set[str] = set()
    runs: set[tuple] = set()
    path = directory / OVERLAY
    if not path.exists():
        return cases, runs
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["kind"] not in ("case", "run"):
            continue
        target, key = (cases, row["case"]) if row["kind"] == "case" else (runs, run_key(row))
        if row.get("undo"):
            target.discard(key)
        else:
            target.add(key)
    return cases, runs


def read_labels(directory: Path = RESEARCH, name: str = FROZEN) -> dict[str, list[str]]:
    """A set's corrected group labels from the overlay ({"kind": "label", "set", "case",
    "groups"}): a frozen set file is never edited, so a wrong label found later is fixed here
    (RULE.md § Retiring a defective case); the newest row for a case wins."""
    path = directory / OVERLAY
    labels: dict[str, list[str]] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            row = json.loads(line) if line.strip() else {}
            if row.get("kind") == "label" and row.get("set") == name:
                labels[row["case"]] = list(row["groups"])
    return labels


def read_log(path: Path = LOG, raw: bool = False) -> list[dict[str, Any]]:
    """A JSONL log's rows. A runs log (an `eval-*.jsonl`) is read through the overlay unless `raw`:
    the runs of a retired case and each redacted run are left out, so no score and no resume
    sees them."""
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if raw or not path.name.startswith("eval-"):
        return rows
    cases, runs = read_overlay(path.parent)
    if not cases and not runs:
        return rows
    # A per-arm log's rows may not name the arm; the file name does (`<prefix><arm>.jsonl`).
    arm = None
    if not path.name.endswith("local.jsonl"):
        prefix = max(
            (s.prefix for s in SETS.values() if path.name.startswith(s.prefix)),
            key=len,
            default="eval-",
        )
        arm = path.stem.removeprefix(prefix)
    return [
        r for r in rows if r.get("case") not in cases and run_key({"arm": arm, **r}) not in runs
    ]


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


class JudgeLimit(RuntimeError):
    """The judge's subscription refused for its usage limit: no later verdict can be had until it
    resets, so the pass stops as on a spent quota and scores no turn (#427)."""


# The Claude judge (#427, RULE.md § Scoring a run): one fresh `claude -p` process a verdict, with
# no tool, no MCP server, no settings and nothing persisted, so it sees only the judge prompt (the
# orchestrating session has read every setup's results; this process has not). The flags are the
# strict runner's (probes/387_cc_strict.py), less its MCP tools.
CLAUDE_JUDGE_ASK = "Grade the answer now, ending with the VERDICT line."
CLAUDE_JUDGE_TIMEOUT_S = 180.0
# Words of a usage-limit refusal in the result of a `claude -p` process (387_cc_strict.LIMIT_WORDS).
CLAUDE_LIMIT_WORDS = ("usage limit", "rate limit", "limit reached", "quota")


def claude_judge_args(model: str, system_prompt: Path) -> list[str]:
    """The `claude -p` arguments for one verdict, after the command itself."""
    return [
        "-p",
        "--model",
        model,
        "--tools",
        "",
        "--strict-mcp-config",
        "--setting-sources",
        "",
        "--no-session-persistence",
        "--system-prompt-file",
        str(system_prompt),
        "--output-format",
        "json",
    ]


def claude_judge(model: str | None = None, command: Sequence[str] = ("claude",)) -> Judge:
    """The judge as one headless Claude Code process per call: the judge prompt is its system
    prompt, the question its only message, and its reply the `result` of the JSON it prints.
    A usage-limit refusal raises JudgeLimit; any other failure (a non-zero exit, an error result,
    unreadable output, a timeout) raises RuntimeError, a failed request the pass may skip."""
    from semantic_agent.model import claude_judge_model

    model = model or claude_judge_model()

    async def ask(prompt: str) -> str:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            system = Path(tmp, "judge.md")
            system.write_text(prompt)
            proc = await asyncio.create_subprocess_exec(
                *command,
                *claude_judge_args(model, system),
                cwd=tmp,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, err = await asyncio.wait_for(
                    proc.communicate(CLAUDE_JUDGE_ASK.encode()), CLAUDE_JUDGE_TIMEOUT_S
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                raise RuntimeError(
                    f"claude -p gave no verdict in {CLAUDE_JUDGE_TIMEOUT_S:.0f} s"
                ) from None
        try:
            event = json.loads(out.decode() or "{}")
        except json.JSONDecodeError:
            event = {}
        result = str(event.get("result") or "")
        said = " ".join((result + " " + err.decode(errors="replace")).split())
        if any(w in said.lower() for w in CLAUDE_LIMIT_WORDS) and (
            event.get("is_error") or proc.returncode or not parse_verdict(result)
        ):
            raise JudgeLimit(said[:300])
        if proc.returncode or event.get("is_error") or not event:
            raise RuntimeError(f"claude -p failed (exit {proc.returncode}): {said[:300]}")
        return result

    return ask


def build_judge(backend: str | None = None) -> Judge:
    """The judge on its backend (model.judge_backend: `claude` by default, `openrouter` behind
    the switch)."""
    from semantic_agent.model import judge_backend

    return claude_judge() if (backend or judge_backend()) == "claude" else model_judge()


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
    concurrency: int = 1,
) -> tuple[str, int]:
    """Ask the judge each verdict the cache lacks for an unclear turn, appending each to `path` as
    it comes; returns why it stopped (`done`, `requests`, `quota`, `limit` or `unavailable`) and
    the requests sent. `JUDGE_FAILURES` failed requests in a row that are not a spent quota (the
    judge model down upstream, #371) stop the pass with "judge unavailable: <error>" printed; a
    usage limit (JudgeLimit) stops it as `limit`. Up to `concurrency` verdicts are asked at once,
    in log order."""
    from semantic_agent.model import classify

    questions = {q.id: q for q in bet.questions}
    described = evaluation.definitions(bet.questions)
    cached = read_verdicts(path, judge_model, bet.name)
    asks: list[tuple[TurnKey, str, str, int]] = []
    for (arm, model, case, run, i), text in undecided_turns(entries, bet.hedges):
        if case not in questions:
            continue
        digest = answer_hash(text)
        have = cached.get((arm, model, case, run, i, digest), [None] * VERDICTS)
        for n in range(1, VERDICTS + 1):
            if have[n - 1] is None:
                asks.append(((arm, model, case, run, i), text, digest, n))
    spent = 0
    failures = 0
    stop: list[str] = []
    queue = iter(asks)

    async def one(key: TurnKey, text: str, digest: str, n: int) -> None:
        nonlocal failures
        arm, model, case, run, i = key
        turn = questions[case].turns[i]
        if turn.kind == "define":
            definition = " ".join(described.get(name, name) for name in turn.define)
            prompt = define_prompt(turn.question, definition, text)
        else:
            prompt = judge_prompt(turn.question, expected[case][i], text)
        try:
            reply = await judge(prompt)
        except JudgeLimit as limit:
            print(f"judge stopped: {limit}")
            stop.append("limit")
            return
        except Exception as error:  # a failed request: asked again on a later pass
            failure = classify(error)
            if failure.ends_run:
                stop.append("quota")
                return
            failures += 1
            if failures >= JUDGE_FAILURES:
                print(f"judge unavailable: {failure.message}")
                stop.append("unavailable")
            return
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

    async def worker() -> None:
        nonlocal spent
        while not stop:
            item = next(queue, None)
            if item is None:
                return
            if requests is not None and spent >= requests:
                stop.append("requests")
                return
            spent += 1
            await one(*item)

    await asyncio.gather(*(worker() for _ in range(max(1, concurrency))))
    return (stop[0] if stop else "done"), spent


def scored_logs(bet: BetSet, directory: Path = RESEARCH) -> list[dict[str, Any]]:
    """Every arm's runs on `bet`'s set scored on read under the current wordings (`recode`), from
    the cached expected numbers when they exist: the one scoring both the report (`judged_logs`)
    and the judge's selection of turns (`--judge`) read, so every turn the report leaves unclear is
    a turn the judge is asked about (#426)."""
    expected = read_expected(bet.name, directory)
    described = evaluation.definitions(bet.questions) if expected is not None else None
    return recode(bet, read_logs(directory, bet.name), expected, described)


def pending_verdicts(
    bet: BetSet, entries: Sequence[dict[str, Any]], judge_model: str, path: Path = JUDGE_LOG
) -> list[tuple[TurnKey, str]]:
    """The judgeable turns (`undecided_turns`) that lack one of their verdicts from `judge_model`
    in the cache at `path`: what a `--judge` pass would ask about."""
    cached = read_verdicts(path, judge_model, bet.name)
    cases = {q.id for q in bet.questions}
    out = []
    for key, text in undecided_turns(entries, bet.hedges):
        if key[2] not in cases:
            continue
        if None in cached.get((*key, answer_hash(text)), [None] * VERDICTS):
            out.append((key, text))
    return out


def judged_logs(bet: BetSet, directory: Path = RESEARCH) -> list[dict[str, Any]]:
    """Every arm's runs on `bet`'s set as scored now (`scored_logs`), with the current judge
    model's verdicts on that set applied."""
    from semantic_agent.model import judge_model_id

    verdicts = read_verdicts(directory / JUDGE_LOG.name, judge_model_id(), bet.name)
    return apply_verdicts(scored_logs(bet, directory), verdicts)


# The warehouse audit beside the logs (#439): `ops.agent_queries` keeps every query_metrics and
# execute_sql call by its ADK session and invocation, but lives in the fixture's database, which a
# rebuild drops; each local pass appends the rows it has not exported yet, so a run's calls join
# to it (`audit_join`) from the repo alone.
AUDIT = "audit-queries.jsonl"
AUDIT_COLUMNS = (
    "called_at",
    "agent",
    "tool",
    "session_id",
    "invocation_id",
    "call_id",
    "metrics",
    "filters",
    "arguments",
    "sql",
    "rows_returned",
    "freshness",
    "error",
)


def export_audit(url: str, directory: Path = RESEARCH) -> int:
    """Append the audit rows newer than the last one exported; returns how many."""
    import psycopg

    path = directory / AUDIT
    last = max((r["called_at"] for r in read_log(path)), default=None)
    query = f"select {', '.join(AUDIT_COLUMNS)} from ops.agent_queries"
    params: list[Any] = []
    if last is not None:
        query += " where called_at > %s::timestamptz"
        params.append(last)
    with psycopg.connect(url) as conn:
        rows = conn.execute(query + " order by called_at", params).fetchall()
    for row in rows:
        out = dict(zip(AUDIT_COLUMNS, row, strict=True))
        out["called_at"] = out["called_at"].isoformat()
        append_log(json.loads(json.dumps(out, default=str)), path)
    return len(rows)


def audit_join(
    entries: Sequence[dict[str, Any]], audit: Sequence[dict[str, Any]]
) -> dict[tuple, list[dict[str, Any]]]:
    """Each logged run that names its session, with the audit rows of that session."""
    by_session: dict[str, list[dict[str, Any]]] = {}
    for row in audit:
        if row.get("session_id"):
            by_session.setdefault(row["session_id"], []).append(row)
    return {run_key(e): by_session.get(e["session_id"], []) for e in entries if e.get("session_id")}


# Each set's expected numbers, read once from the fixture warehouse (`--write-expected`), so the
# logs are scored again on read in full whenever the reading of an answer changes (#382). The
# fixture is deterministic; the file names the database it was read from.
EXPECTED = "expected.json"


def read_expected(name: str, directory: Path = RESEARCH) -> dict[str, Expected] | None:
    path = directory / EXPECTED
    if not path.exists():
        return None
    return json.loads(path.read_text()).get("sets", {}).get(name)


def write_expected(url: str, directory: Path = RESEARCH) -> Path:
    """Every set's expected numbers per case and turn, from the warehouse at `url` (retired cases
    included, so an undo needs no new read)."""
    whole = Path("/nonexistent")
    sets = {}
    for name, files in SETS.items():
        questions = load_bet(files.questions, name=name, overlay=whole).questions
        sets[name] = evaluation.expected_numbers(questions, url)
    path = directory / EXPECTED
    written = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")
    database = url.rsplit("/", 1)[-1]
    payload = {"written": written, "database": database, "sets": sets}
    path.write_text(json.dumps(payload, indent=0) + "\n")
    return path


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
    every = {q.id for q in bet.questions}
    managed: list[tuple[float, int, str, str]] = []
    partial: list[tuple[float, int, str, str]] = []
    for model in models:
        for arm in arms_of(entries, model):
            if RUNG.get(arm, 9) > 2:
                continue
            # Ranked by its own accuracy over every case it finished (the shares step 2 pairs),
            # not over the cases every arm on its model reached; and only an arm that answered
            # every case can be the best: a pass under way scores on a handful (2026-11-04).
            right = case_shares(entries, arm, model, runs)[0]
            if not right:
                continue
            accuracy = sum(right.values()) / len(right)
            whole = every <= set(right)
            (managed if whole else partial).append((accuracy, RUNG[arm], arm, model))
    managed = managed or partial
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
    lines += step_three(sets, runs)
    return lines


def ties_with_best(
    bet: BetSet, entries: Sequence[dict[str, Any]], runs: int = RUNS
) -> dict[tuple[str, str], Interval] | None:
    """Every arm on every model it ran with whose accuracy shows no difference from the managed
    best on the cases both reached (the best itself included), with its paired interval; None
    while there is no managed best."""
    managed, _, _ = step_two(bet, entries, runs)
    if managed is None:
        return None
    best, best_model, _ = managed
    best_right, _, _ = case_shares(entries, best, best_model, runs)
    tied: dict[tuple[str, str], Interval] = {}
    for model in dict.fromkeys(e["model"] for e in entries):
        for arm in arms_of(entries, model):
            if arm not in RUNG:
                continue
            right, _, _ = case_shares(entries, arm, model, runs)
            # A tie needs every case: a pass under way reads "no difference" on a handful.
            if not {q.id for q in bet.questions} <= set(right):
                continue
            cases = sorted(set(right) & set(best_right))
            acc = paired_interval({c: best_right[c] for c in cases}, {c: right[c] for c in cases})
            if (arm, model) == (best, best_model) or not acc.differs:
                tied[(arm, model)] = acc
    return tied


def step_three(
    sets: Mapping[str, tuple[BetSet, Sequence[dict[str, Any]]]], runs: int = RUNS
) -> list[str]:
    """RULE.md § The rule, 3, on both sets (#356): the arms with no accuracy difference from each
    set's managed best on every set, and the cheapest rung among them; a tie within that rung goes
    to the arm with fewer moving parts named in its finding, which the report names."""
    titles = {name: SETS[name].title for name in sets}
    ties = {name: ties_with_best(bet, entries, runs) for name, (bet, entries) in sets.items()}
    if any(t is None for t in ties.values()):
        missing = " or ".join(titles[n] for n, t in ties.items() if t is None)
        return [f"- Step 3 cannot apply yet: no managed best on {missing}."]
    found = [t for t in ties.values() if t is not None]
    common = [key for key in found[0] if all(key in t for t in found[1:])]
    if not common:
        return ["- Step 3: no arm shows no accuracy difference from the managed best on both sets."]
    listed = ", ".join(f"`{a}` on `{m}` (rung {RUNG[a]})" for a, m in common)
    rung = min(RUNG[a] for a, _ in common)
    cheapest = ", ".join(f"`{a}` on `{m}`" for a, m in common if RUNG[a] == rung)
    return [
        "- Step 3 (RULE.md § The rule, 3; it applies when no arm of ours is worth building): the "
        f"arms with no accuracy difference from the managed best on both sets: {listed}.",
        f"  The cheapest rung among them is {rung}: {cheapest}; within a rung the arm with fewer "
        "moving parts named in its finding wins (§ The cost ladder), which the report names.",
    ]


# Each tool result kept in the log is cut to this many characters (bet_live's RESULT_HEAD).
RESULT_HEAD = 400


def tool_calls(invocation: Invocation) -> list[dict[str, Any]]:
    """One answered turn's tool calls as the probes' logs carry them: name, arguments and the head
    of the result, matched by call id (#388)."""
    data = invocation.intermediate_data
    if data is None:
        return []
    results = {
        r.id: json.dumps(r.response, default=str)[:RESULT_HEAD]
        for r in get_all_tool_responses(data)
        if r.id
    }
    return [
        {"tool": use.name, "args": dict(use.args or {}), "result": results.get(use.id or "", "")}
        for use in get_all_tool_calls(data)
    ]


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


# The canary (2026-11-04: an Opus pass with no audit database answered 3 of 288 right and spent
# $16.31 before anyone saw): before a pass, each arm answers the set's first single-turn `covered`
# case, unlogged; two misses stop the pass. Every healthy arm measured answers such a case.
CANARY_TRIES = 2


# Each set's canary: the single-turn case every arm on every model answered right in every run
# logged by 2026-11-04T19:20Z (about 20 arm-model pairs a set, the bare data agent included); the
# first covered case is not enough: the bare agent missed the hard set's first one honestly.
# hard-v2 carries the hard set's canary unchanged (#377).
CANARIES = {
    "frozen": "orders_one_day",
    "hard": "hard_top_channel_bookings",
    "hard-v2": "hard_top_channel_bookings",
}


# A setup whose tools cannot reach a set's canary by design takes another set's canary: the canary
# checks the warehouse, the agent and the model, and a miss of reach stops a healthy pass.
# Lightdash serves one explore per model with no joins, and the 2026-11-07 lane's custom-lightdash
# answered the hard sets' canary by campaign ("channel is not a dimension on slv_bookings"), twice,
# minutes after passing the frozen canary. The hard case is still asked and scored like any other.
CANARY_SET = {"custom-lightdash": FROZEN}


def arm_canary(
    bet: BetSet, arm: str, expected: Mapping[str, Expected], described: Mapping[str, str]
) -> tuple[Question | None, BetSet, Mapping[str, Expected], Mapping[str, str]]:
    """The canary `arm` answers before a pass on `bet`, with the set, expected numbers and
    definitions it is scored against: the set's own (canary_case), unless CANARY_SET names
    another set for the arm, whose canary and recorded expected numbers it then takes."""
    other = CANARY_SET.get(arm)
    if other is None or other == bet.name:
        return canary_case(bet), bet, expected, described
    probe_set = load_set(other)
    probe = canary_case(probe_set)
    recorded = read_expected(other) or {}
    if probe is None or probe.id not in recorded:
        return canary_case(bet), bet, expected, described
    return probe, probe_set, recorded, evaluation.definitions([probe])


def canary_case(bet: BetSet) -> Question | None:
    """The set's canary (CANARIES), else its first single-turn case in the `covered` group."""
    by_id = {q.id: q for q in bet.questions}
    if (named := CANARIES.get(bet.name)) in by_id:
        return by_id[named]
    return next(
        (q for q in bet.questions if len(q.turns) == 1 and "covered" in bet.groups.get(q.id, [])),
        None,
    )


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
    canary: bool = False,
) -> str:
    """Ask every (run, case, arm) the log has not finished, in that order, so a cut run still
    leaves both arms paired on the cases it reached. With `canary`, each arm first answers the
    set's canary case (canary_case), unlogged, and a pass whose arm misses it twice stops as
    `canary` before it spends on the rest. Returns why it stopped: `done`, `quota`
    (the model's quota or key ended the run), `time` (past the deadline), `requests` (this pass
    spent its share of the shared free quota) or `budget` (its Claude dollars, spend.METER).
    The runs of an arm in `legacy` (its agent has the legacy tables in reach, and `silver` since
    #445) are logged with `"legacy": true` and `"reach": REACH`."""
    spent = 0
    probe = canary_case(bet) if canary else None
    for arm in [a for a in ARMS if a in agents] if probe else []:
        if all(
            (arm, run, q.id) in finished(read_log(log), model)
            for run in range(1, runs + 1)
            for q in bet.questions
        ):
            continue
        for attempt in range(1, CANARY_TRIES + 1):
            cases = evaluation.eval_cases(
                [probe],
                dict(expected),
                agents[arm].name,
                arm == "custom-metricflow",
                dict(described),
            )
            mark = spend.METER.begin_case(model, arm=arm, run=0, case=probe.id)
            outcome = (await evaluation.evaluate(agents[arm], cases, [ANSWER_CORRECT]))[probe.id]
            spend.METER.end_case(mark)
            spent += outcome.model_calls
            if outcome.skipped or outcome.ends_run:
                return "budget" if spend.METER.stopped else "quota"
            turns = score_case(probe, expected[probe.id], outcome.inferences, bet.hedges, described)
            if run_outcome([o for _, o in turns]) is Outcome.RIGHT:
                break
            text = " ".join((turns[-1][0] if turns else outcome.error or "").split())[:200]
            print(f"canary: {arm} missed {probe.id} (try {attempt}): {text}")
        else:
            print(
                f"stopped: canary: {arm} missed {probe.id} {CANARY_TRIES} times; check the "
                "warehouse, the agent and the model before spending on the rest"
            )
            return "canary"
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
                    entry["reach"] = REACH
                if usage.calls:
                    entry["usage"] = usage.as_dict()
                if outcome.error:
                    entry["error"] = " ".join(outcome.error.split())[:300]
                    append_log(entry, log)
                    continue
                # #388: every call the agent made, and a run outside its setup's tools unscored.
                calls = [tool_calls(i) for i in outcome.inferences]
                if strays := bet_tools.outside(arm, [{"calls": c} for c in calls]):
                    print(f"{question.id} run {run}: not scored, outside {arm}'s tools: {strays}")
                    bet_tools.write_fault(
                        {**entry, "turns": [{"calls": c} for c in calls]}, strays, log.parent
                    )
                    continue
                turns = score_case(
                    question, expected[question.id], outcome.inferences, bet.hedges, described
                )
                # #439: the ADK session and each turn's invocation, which ops.agent_queries keys
                # its rows on, so the warehouse audit joins to the run.
                if outcome.session_id:
                    entry["session_id"] = outcome.session_id
                entry["turns"] = [
                    {
                        "text": t,
                        "outcome": o.value,
                        "calls": c,
                        **({"invocation_id": i.invocation_id} if i.invocation_id else {}),
                    }
                    for (t, o), c, i in zip(turns, calls, outcome.inferences, strict=False)
                ]
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
        if set(DEFAULT_ARMS) <= set(arms):
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
        bet = load_set(name, overlay=directory)
        scored[name] = (bet, judged_logs(bet, directory))
        lines += ["", report(bet, scored[name][1], runs, every_arm=True, depth=1).rstrip("\n")]
    # The last set's section ends with both deciding sets' verdict (RULE.md § Changes since
    # freezing); a set version not yet adopted (§ Set versions) is shown, never deciding.
    lines += both_sets({n: scored[n] for n in DECIDING}, runs, depth=1)
    return "\n".join(lines).rstrip("\n") + "\n"


def write_every_arm(directory: Path = RESEARCH, runs: int = RUNS) -> Path:
    path = directory / ALL_REPORT.name
    path.write_text(every_arm_report(directory, runs))
    (directory / RESULTS.name).write_text(
        json.dumps(results(directory, runs), indent=1, ensure_ascii=False) + "\n"
    )
    write_scored_runs(directory)
    return path


SCORED_RUNS = "scored-runs.jsonl"
EXAMPLE_TEXT = 400


def write_scored_runs(directory: Path = RESEARCH) -> Path:
    """Every run of every set as it is scored now (the overlay applied, every turn scored again,
    the judge's verdicts in), for the report: it reads its squares and examples from here, never
    from the logs, so it shows only the current data (#382; owner, 2026-11-06: "uses the latest
    the freshest data points only"). One row per run: its key, its outcome, and per turn the
    outcome, the head of the answer and the tools it called."""
    rows = []
    for name in SETS:
        bet = load_set(name, overlay=directory)
        for e in judged_logs(bet, directory):
            if e.get("case") not in bet.groups:
                continue
            turns = [
                {
                    "outcome": t.get("outcome"),
                    "text": (t.get("text") or "")[:EXAMPLE_TEXT],
                    "tools": sorted({c.get("tool") for c in t.get("calls") or [] if c.get("tool")}),
                }
                for t in e.get("turns") or []
            ]
            keep = ("arm", "model", "case", "run", "at", "outcome", "carried_from")
            rows.append({"set": name, **{k: e[k] for k in keep if k in e}, "turns": turns})
    path = directory / SCORED_RUNS
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return path


RESULTS = RESEARCH / "results.json"
CALLS = RESEARCH / "findings" / "2026-11-03-361-claude-calls.jsonl"


def harness(model: str) -> str:
    """What ran the model (owner, 2026-11-04: kept as metadata and a sanity check, so a difference
    between the same model behind the API and behind a Claude Code subagent is visible in the data):
    Google's data-agent service, a Claude Code subagent on the subscription (#374), ADK on the
    Anthropic API, or ADK on OpenRouter."""
    if model.startswith("google-data-agent"):
        return "google-data-agent"
    if model.startswith("claude-code-strict"):
        return "claude-code-headless"
    if model.startswith("claude-code"):
        return "claude-code-subagent"
    if model.startswith("claude-"):
        return "adk-anthropic-api"
    return "adk-openrouter"


def session_kind(model: str) -> str:
    """How many questions shared a session: one run per fresh session (RULE.md, every harness but
    the batched subagents), or one batch of about 12 cases per Claude Code subagent (#374's first
    pass, 2026-11-04), or one case per fresh subagent (`fresh-<model>`, the matched rerun, and
    `subject-<model>`, the Bash-and-Read-only agent type, also one fresh subagent per case)."""
    if model.startswith("claude-code-strict"):
        return "fresh per run"
    if model.startswith(("claude-code (fresh-", "claude-code (subject-")):
        return "fresh per case"
    if model.startswith("claude-code"):
        return "shared per batch"
    return "fresh per run"


def arm_result(
    bet: BetSet, entries: Sequence[dict[str, Any]], arm: str, model: str, runs: int
) -> dict[str, Any]:
    """One arm on one model on one set, over every case it finished: the two numbers with their
    bootstrap intervals, each group's accuracy, pass^k, the outcomes and the model responses."""
    right, wrong, ran = case_shares(entries, arm, model, runs)
    zero = dict.fromkeys(right, 0.0)
    acc, cw = paired_interval(zero, right), paired_interval(zero, wrong)
    done = finished(entries, model)
    outcomes: dict[str, int] = {}
    per_case: dict[str, list[str]] = {}
    for (a, run, case), outcome in done.items():
        if a == arm and run <= runs:
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            per_case.setdefault(case, []).append(outcome)
    groups: dict[str, list[float]] = {}
    for case, share in right.items():
        for group in bet.groups.get(case, []):
            groups.setdefault(group, []).append(share)
    calls = sum(
        int(e.get("model_calls") or 0) for e in entries if e["arm"] == arm and e["model"] == model
    )
    # A set version's new cases on their own (RULE.md § Set versions: hard-v2's criteria read them):
    # all of them, then by group.
    new: dict[str, list[float]] = {}
    for case in bet.new:
        if case in right:
            new.setdefault("all", []).append(right[case])
            for group in bet.groups.get(case, []):
                new.setdefault(group, []).append(right[case])
    carried = sum(
        1
        for e in entries
        if e["arm"] == arm and e["model"] == model and e.get("carried_from") and e["run"] <= runs
    )
    return {
        "set": bet.name,
        "arm": arm,
        "model": model,
        "harness": harness(model),
        "session": session_kind(model),
        "rung": RUNG.get(arm),
        "cases": len(right),
        "of_cases": len(bet.questions),
        "runs": ran,
        "accuracy": [acc.mean, acc.low, acc.high],
        "confident_wrong": [cw.mean, cw.low, cw.high],
        "groups": {g: [sum(v) / len(v), len(v)] for g, v in sorted(groups.items())},
        "pass_all": sum(all(o == "right" for o in r) for r in per_case.values()) / len(per_case)
        if per_case
        else None,
        "outcomes": outcomes,
        "model_calls": calls,
        **(
            {"new": {g: [sum(v) / len(v), len(v)] for g, v in sorted(new.items())}}
            if bet.new
            else {}
        ),
        **({"carried_runs": carried} if carried else {}),
    }


def question_set(name: str, directory: Path = RESEARCH) -> dict[str, Any]:
    """What the question-set section of the report shows of one set (#390): its freeze date, hash,
    what it supersedes, and every case as written (retired ones too, with the register's reason):
    its turns, groups, kinds, SQL-rubric kinds and expected numbers (expected.json)."""
    path = SETS[name].questions
    text = path.read_text()
    spec = yaml.safe_load(text)
    expected = (read_expected_raw(directory) or {}).get(name, {})
    reasons = {}
    overlay = directory / OVERLAY
    for line in overlay.read_text().splitlines() if overlay.exists() else []:
        row = json.loads(line)
        if row.get("kind") == "case":
            reasons[row["case"]] = (
                None
                if row.get("undo")
                else {
                    "class": row.get("class"),
                    "reason": row.get("reason"),
                    "date": row.get("date"),
                }
            )
    kinds = spec.get("kinds") or {}
    rubric = spec.get("rubric") or {}
    new = set(spec.get("new") or ())
    cases = []
    for q in spec["questions"]:
        turns = q.get("turns") or [q]
        cases.append(
            {
                "id": q["id"],
                "turns": [t["question"] for t in turns],
                "groups": (spec.get("groups") or {}).get(q["id"], []),
                "kinds": kinds.get(q["id"], []),
                "rubric": rubric.get(q["id"], []),
                "naive": q["id"] in (spec.get("naive_sql") or {}),
                "new": q["id"] in new,
                "expected": expected.get(q["id"]),
                "retired": reasons.get(q["id"]),
            }
        )
    return {
        "frozen": str(spec.get("frozen") or ""),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "supersedes": spec.get("supersedes"),
        "supersedes_why": " ".join(str(spec.get("supersedes_why") or "").split()) or None,
        "questions": cases,
    }


def read_expected_raw(directory: Path = RESEARCH) -> dict[str, Any] | None:
    path = directory / EXPECTED
    return json.loads(path.read_text())["sets"] if path.exists() else None


def results(directory: Path = RESEARCH, runs: int = RUNS) -> dict[str, Any]:
    """results.json: every number eval.md shows, as data, for the report and its charts (#336):
    each arm on each model on each set, step 2's pairs against each set's managed best, step 3's
    ties, and the Claude spend by pass from the calls log."""
    out: dict[str, Any] = {
        "written": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "rule": "RULE.md",
        "arms": [],
        "step_two": [],
        "step_three": {},
        "managed_best": {},
        # RULE.md § Set versions: which sets decide, and what each version supersedes.
        "deciding_sets": list(DECIDING),
        "set_versions": {
            name: yaml.safe_load(files.questions.read_text()).get("supersedes")
            for name, files in SETS.items()
        },
    }
    from semantic_agent.model import judge_model_id

    judge = judge_model_id()
    out["judge"] = judge
    out["sets"] = {}
    retired, _ = read_overlay(directory)
    for name in SETS:
        bet = load_set(name, overlay=directory)
        out["sets"][name] = {
            "cases": [q.id for q in bet.questions],
            "groups": bet.groups,
            "new": list(bet.new),
            "retired": sorted(c for c in retired if c in yaml_ids(SETS[name].questions)),
            **question_set(name, directory),
        }
        # Turns no verdict of the current judge has settled yet (#426): each counts as wrong, and a
        # confident-wrong one waiting on its hedge as confident-wrong, until it is judged.
        out["sets"][name]["judge_waiting"] = len(
            pending_verdicts(bet, scored_logs(bet, directory), judge, directory / JUDGE_LOG.name)
        )
        entries = judged_logs(bet, directory)
        for model in dict.fromkeys(e["model"] for e in entries):
            for arm in arms_of(entries, model):
                if case_shares(entries, arm, model, runs)[2]:
                    out["arms"].append(arm_result(bet, entries, arm, model, runs))
        managed, _, paired = step_two(bet, entries, runs)
        out["managed_best"][name] = list(managed) if managed else None
        for p in paired:
            out["step_two"].append(
                {
                    "set": name,
                    "arm": p.arm,
                    "model": p.model,
                    "cases": p.cases,
                    "runs": p.ran,
                    "accuracy": [p.accuracy.mean, p.accuracy.low, p.accuracy.high],
                    "confident_wrong": [
                        p.confident_wrong.mean,
                        p.confident_wrong.low,
                        p.confident_wrong.high,
                    ],
                    "worth": p.worth,
                }
            )
        ties = ties_with_best(bet, entries, runs)
        out["step_three"][name] = sorted(f"{a} on {m}" for a, m in ties) if ties else None
    spend: dict[str, dict[str, Any]] = {}
    calls_log = directory / CALLS.relative_to(RESEARCH)
    if calls_log.exists():
        for line in calls_log.read_text().splitlines():
            row = json.loads(line)
            entry = spend.setdefault(row.get("pass") or "?", {"model": row.get("model"), "usd": 0})
            entry["usd"] = round(entry["usd"] + float(row.get("dollars") or 0), 6)
    out["claude_spend_by_pass"] = spend
    return out


def warehouse_unreachable() -> str | None:
    """Why a pass cannot start: the metric or audit login the agents use does not connect (one
    `select 1` each, 5 s), so no run is logged whose answer is an infrastructure failure."""
    import psycopg

    from semantic_agent.warehouse_postgres import audit_url, read_url

    for name, url in (("audit", audit_url()), ("metrics", read_url())):
        try:
            with psycopg.connect(url, connect_timeout=5) as conn:
                conn.execute("select 1")
        except psycopg.Error as error:
            first = (str(error).strip().splitlines() or [type(error).__name__])[0]
            return f"the {name} database is unreachable ({first}): no run asked"
    return None


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
    parser.add_argument("--arms", nargs="*", default=list(DEFAULT_ARMS), choices=ARMS)
    parser.add_argument(
        "--no-canary", action="store_true", help="skip the canary case before a pass (CANARY_TRIES)"
    )
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
        "--judge-backend",
        choices=("claude", "openrouter"),
        default=None,
        help="the judge's backend: claude (Haiku through claude -p, the default) or openrouter",
    )
    parser.add_argument(
        "--concurrency", type=int, default=1, help="verdicts asked at once by --judge"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="with --judge: count the turns waiting, ask none"
    )
    parser.add_argument(
        "--export-audit",
        action="store_true",
        help="append the fixture's new ops.agent_queries rows to audit-queries.jsonl (#439)",
    )
    parser.add_argument(
        "--write-expected",
        action="store_true",
        help="read every set's expected numbers from the warehouse into expected.json (#382)",
    )
    parser.add_argument(
        "--set",
        dest="which",
        default=FROZEN,
        choices=list(SETS),
        help="the set asked, logged and scored (default: the frozen set)",
    )
    args = parser.parse_args(argv)
    if args.judge_backend:
        # The report written below reads this backend's verdicts too (model.judge_model_id).
        os.environ["BET_JUDGE_BACKEND"] = args.judge_backend

    from semantic_agent.model import DEFAULT_MODEL_ID, MissingKey, claude_key, judge_model_id

    model = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    claude = os.environ.get("MODEL_BACKEND", "openrouter") == "anthropic"
    files = SETS[args.which]
    local_log = files.local_log()
    log = args.log or local_log
    bet = load_set(args.which)
    why = "report"
    if args.write_expected:
        database = os.environ.get("DBT_DBNAME", "dbt_dev")
        url = os.environ.get(
            "WAREHOUSE_OWNER_URL", f"postgresql://warehouse:warehouse@localhost:5433/{database}"
        )
        print(f"expected numbers: written to {write_expected(url)}")
        return 0
    owner_db = os.environ.get("DBT_DBNAME", "dbt_dev")
    owner = os.environ.get(
        "WAREHOUSE_OWNER_URL", f"postgresql://warehouse:warehouse@localhost:5433/{owner_db}"
    )
    if args.export_audit:
        print(f"audit: {export_audit(owner)} row(s) appended to {RESEARCH / AUDIT}")
        return 0
    if args.judge:
        # The turns the report leaves unclear, scored as it scores them (#426): from the cached
        # expected numbers (`--write-expected`), which the prompts show too.
        logs = scored_logs(bet)
        judge_id = judge_model_id()
        waiting = pending_verdicts(bet, logs, judge_id, JUDGE_LOG)
        print(
            f"judge: {len(waiting)} turn(s) of {args.which} wait for a verdict of {judge_id} "
            f"({len(undecided_turns(logs, bet.hedges))} judgeable)"
        )
        if args.dry_run:
            return 0
        pending = {key[2] for key, _ in waiting}
        asked = load_set(args.which, sorted(pending)) if pending else BetSet([], {}, [], args.which)
        expected = read_expected(args.which) or {}
        if pending and not expected:
            print("stopped: no expected.json; write it first (--write-expected)")
            return 2
        why, spent = await judge_turns(
            asked,
            logs,
            expected,
            build_judge(),
            judge_id,
            JUDGE_LOG,
            args.requests,
            args.concurrency,
        )
        print(f"judge: {spent} request(s) sent to {judge_id}; stopped: {why}")
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
        # The agents reach the Compose warehouse from the host by its published port, as the owner
        # URL below does; without these the metric and audit connections default to the in-cluster
        # `warehouse:5432`, and every metric query is withheld for its unwritten audit row (an Opus
        # pass, 2026-11-04: 219 of 288 runs answered "the audit record could not be written").
        os.environ.setdefault("DBT_HOST", "localhost")
        os.environ.setdefault("DBT_PORT", "5433")
        # A Claude pass without its key is skipped before anything else: it needs no warehouse.
        if claude:
            try:
                claude_key()
            except MissingKey as missing:
                print(f"skipped: {missing}")
                return 3
        if problem := warehouse_unreachable():
            print(f"stopped: {problem}")
            return 2
        from semantic_agent.agent import build_agent as build_semantic
        from semantic_agent.hybrid import build_agent as build_hybrid
        from semantic_agent.toolset_metricflow import toolset_compute
        from sql_baseline.agent import build_agent as build_baseline

        asked = load_set(args.which, args.ids) if args.ids else bet
        database = os.environ.get("DBT_DBNAME", "dbt_dev")
        owner_url = os.environ.get(
            "WAREHOUSE_OWNER_URL", f"postgresql://warehouse:warehouse@localhost:5433/{database}"
        )
        expected = evaluation.expected_numbers(asked.questions, owner_url)
        described = evaluation.definitions(asked.questions)
        # custom-metricflow's tools read only the semantic models: legacy stays out of its reach.
        sql_reach = (*LEGACY_TABLES, *(reach_tables() if LEGACY_REACH & set(args.arms) else ()))
        if LEGACY_REACH & set(args.arms) and not any(t.startswith("silver.") for t in sql_reach):
            print("stopped: agent_sql reads no silver table; rebuild the fixture (#445)")
            return 2
        builders = {
            "baseline": lambda: build_baseline(extra_tables=sql_reach),
            "custom-metricflow": build_semantic,
            "custom-hybrid": lambda: build_hybrid(extra_tables=sql_reach),
            "custom-metricflow-compute": lambda: build_semantic(toolset=toolset_compute()),
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
            canary=not args.no_canary,
        )
        try:
            print(f"audit: {export_audit(owner)} row(s) appended to {RESEARCH / AUDIT}")
        except Exception as error:  # the runs are logged either way; the next pass exports
            print(f"audit: not exported ({error})")
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
        return 0 if why == "done" else 2 if why == "canary" else 3
    verdicts = read_verdicts(JUDGE_LOG, judge_model_id(), args.which)
    text = report(bet, apply_verdicts(recode(bet, read_log(local_log)), verdicts), args.runs)
    local_report = files.local_report()
    local_report.write_text(text)
    print(text)
    print(f"stopped: {why}; written to {local_report}")
    # eval.md and results.json are scored at the rule's k whatever this pass asked, as
    # 328_mcp_live.py writes them: a k = 1 pass would otherwise cut every arm's runs 2 and 3.
    print(f"every arm: written to {write_every_arm()}")
    if args.judge:
        return 0 if why == "done" else 2 if why == "canary" else 3
    complete = all(score_log(bet, read_log(local_log), m, args.runs).complete for m in [model])
    return 0 if complete else 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
