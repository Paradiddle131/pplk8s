"""Tie every figure in an answer to the tool result it came from (#403, offline part).

`check_turn` reads one turn of an agent's conversation, its question, its answer and its tool calls,
and says for every figure in the answer where it came from, and for every method the answer claims
whether the trace shows it:
- a figure is `cited` when a tool result of the turn, or of an earlier turn of the conversation,
  holds it at the answer's precision, a rate also as a percentage (0.1667 cites 16.67%); `derived`
  when it equals the sum, difference, product, ratio or percentage change of two such figures (the
  question's own numbers count as operands), within the answer's rounding; `untraced` otherwise.
  Dates, clock times, years, ordinals, numbered-list markers, a quoted freshness statement and the
  question's own numbers are not figures. A scale word scales the figure and its precision
  (`€1.85k` is 1850 to the nearest 10).
- a method claim is a phrase naming Python, a regression, k-means or clustering, a forecast, ARIMA,
  a correlation, or a scan of all or every row, in a sentence that neither negates nor hedges it
  ("cannot", "would need", "without"). It is `supported` when the trace shows the method: Python
  only if a call to a tool named like python ran; a statistical method only if a call's arguments
  (its SQL or code) name it; a full scan only if a call ran SQL with no LIMIT.

The check is deterministic and needs nothing but text: it does not judge whether a figure is right,
only whether the trace could have produced it.

Usage: python -m semantic_agent.evidence [--questions YAML]... [--examples N] [--result-cap N]
  LOG...
Each LOG is JSONL, one row a case-run: `arm` (or `setup`), `model`, `run`, `case` and `turns`, each
turn with its `answer` (or `text`), its `question` (or, from the `--questions` set the case comes
from, the case's turn), an optional `outcome` and `calls` of `{tool, args, result}`. A turn is
checked only when it made calls and every call carries its result; the rest are counted as not
checkable. Prints, per arm and model, the turns checked and the share with any untraced figure and
with any unsupported method claim, overall and over the turns scored right. A log that keeps only
each result's head (`--result-cap`, its length) hides the figures past it, so the same shares are
also given over the turns whose results all came through whole.
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

FigureStatus = Literal["cited", "derived", "untraced"]
ClaimStatus = Literal["supported", "unsupported"]


@dataclass(frozen=True)
class Call:
    """One tool call: its tool's name, its arguments and its result text (None: not logged)."""

    tool: str
    args: Mapping[str, Any] = field(default_factory=dict)
    result: str | None = None


@dataclass(frozen=True)
class Figure:
    """A number the answer states. `source` is the result's number it matched or the arithmetic."""

    text: str
    value: float
    status: FigureStatus
    source: str | None = None


@dataclass(frozen=True)
class MethodClaim:
    """A method the answer says it used; `evidence` names the call that shows it."""

    method: str
    phrase: str
    status: ClaimStatus
    evidence: str | None = None


@dataclass(frozen=True)
class Verdict:
    figures: list[Figure]
    methods: list[MethodClaim]

    @property
    def untraced(self) -> list[Figure]:
        return [f for f in self.figures if f.status == "untraced"]

    @property
    def unsupported(self) -> list[MethodClaim]:
        return [m for m in self.methods if m.status == "unsupported"]


# --- figures --------------------------------------------------------------------------------------

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_DAYS = rf"{_DAY}(?:\s*(?:,|and|to|&|-|–|—|through)\s*{_DAY})*"
_NOT_FIGURES = re.compile(
    "|".join(
        [
            r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?",
            r"\b\d{4}-\d{2}\b",  # a month, 2026-10
            rf"\b{_DAYS}\s+(?:of\s+)?{_MONTH}",  # 1 and 2 October, 21–27 Sept
            rf"\b{_MONTH}\s+{_DAYS}\b",  # October 1–2
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
            r"\b\d{1,2}:\d{2}(?::\d{2})?\b",  # clock times
            r"\b\d+(?:st|nd|rd|th)\b",  # ordinals
            r"^\s*\d+[.)](?=\s)",  # numbered-list markers
            r"\b[QH][1-4]\b|\bW\d{1,2}\b",  # quarters, halves, ISO weeks
            # a freshness statement the data call returned (freshness.py) and its deadline
            r"\b(?:Late|Fresh|Freshness unknown):\s.*?(?:deadline\)?|ready up to \S+?|recorded)\.",
            r"\b\d+(?:\s?h|[- ]hours?)\s+(?:freshness\s+)?deadline\b",
        ]
    ),
    re.IGNORECASE | re.MULTILINE,
)
_ANSWER_NUMBER = re.compile(
    r"(?<![\w.\-/])(?P<sign>[-−])?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s?(?P<scale>k|K|thousand|M|mn|million|bn|billion)\b)?"
    r"(?![\w])"
)
_RESULT_NUMBER = re.compile(r"(?<![\w.\-])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w.])")
_SCALES = {
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "mn": 1e6,
    "million": 1e6,
    "bn": 1e9,
    "billion": 1e9,
}
_EPS = 1e-9
_MAX_OPERANDS = 200  # distinct operands for derived figures: 200² pairs a turn


@dataclass(frozen=True)
class _Number:
    text: str
    value: float
    tolerance: float  # half the last stated digit, scaled
    plain_integer: bool  # no decimals, no separators, no scale, no currency: may be a year


def _answer_numbers(text: str) -> list[_Number]:
    text = _NOT_FIGURES.sub(" ", text)
    out = []
    for m in _ANSWER_NUMBER.finditer(text):
        raw = m.group("num").replace(",", "")
        scale = _SCALES[m.group("scale").lower()] if m.group("scale") else 1.0
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        value = float(raw) * scale * (-1 if m.group("sign") else 1)
        before = text[max(0, m.start() - 1) : m.start()]
        plain = raw.isdigit() and "," not in m.group("num") and scale == 1 and before not in "€$£"
        out.append(_Number(m.group(0).strip(), value, 0.5 * 10**-decimals * scale, plain))
    return [n for n in out if not (n.plain_integer and 1900 <= n.value <= 2100)]


def result_numbers(text: str) -> list[float]:
    """The numbers a tool result holds, its dates and timestamps left out."""
    text = _NOT_FIGURES.sub(" ", text)
    out = []
    for raw in _RESULT_NUMBER.findall(text):
        try:
            out.append(float(raw))
        except ValueError:  # pragma: no cover - the pattern only matches floats
            continue
    return out


def _matches(value: float, tolerance: float, candidate: float) -> bool:
    """Equal at the answer's precision, as stated or as a percentage of a rate."""
    slack = tolerance + _EPS * max(1.0, abs(value))
    return (
        abs(abs(value) - abs(candidate)) <= slack or abs(abs(value) - abs(100 * candidate)) <= slack
    )


def _cited(n: _Number, pool: Sequence[float]) -> float | None:
    return next((p for p in pool if _matches(n.value, n.tolerance, p)), None)


def _derivations(operands: Sequence[float]) -> list[tuple[float, str]]:
    ops = list(dict.fromkeys(operands))[:_MAX_OPERANDS]
    out: list[tuple[float, str]] = []
    for i, a in enumerate(ops):
        for b in ops[i + 1 :]:
            out.append((a + b, f"{a:g} + {b:g}"))
            out.append((abs(a - b), f"{a:g} - {b:g}"))
            out.append((a * b, f"{a:g} × {b:g}"))
            for x, y in ((a, b), (b, a)):
                if y:
                    out.append((x / y, f"{x:g} / {y:g}"))
                    out.append(((x - y) / y, f"({x:g} - {y:g}) / {y:g}"))
    return sorted((abs(v), d) for v, d in out)


def _derived(n: _Number, table: Sequence[tuple[float, str]]) -> str | None:
    keys = [v for v, _ in table]
    slack = n.tolerance + _EPS * max(1.0, abs(n.value))
    for target, tol in ((abs(n.value), slack), (abs(n.value) / 100, slack / 100)):
        i = bisect.bisect_left(keys, target - tol)
        if i < len(keys) and keys[i] <= target + tol:
            return table[i][1]
    return None


# --- method claims --------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Method:
    name: str
    claim: re.Pattern[str]
    trace: re.Pattern[str] | None  # in a call's arguments; None: see _supported


_I = re.IGNORECASE
METHODS = (
    _Method(
        "python", re.compile(r"\b(?:python|pandas|numpy|scipy|sklearn|scikit-learn)\b", _I), None
    ),
    _Method(
        "regression",
        re.compile(r"\b(?:regression|regressed|least[-\s]squares|ols)\b", _I),
        re.compile(r"regr_|linear_reg|linregress|polyfit|regression|\bols\b", _I),
    ),
    _Method(
        "clustering",
        re.compile(r"\bk-?means\b|\bclustering\b|\bclustered\b|\bclusters?\b", _I),
        re.compile(r"k[-_]?means|cluster", _I),
    ),
    _Method(
        "forecast",
        re.compile(r"\bforecast(?:s|ed|ing)?\b", _I),
        re.compile(r"forecast|arima|timesfm|prophet|holt|exponential.smoothing", _I),
    ),
    _Method("arima", re.compile(r"\barima(?:_plus)?\b", _I), re.compile(r"arima", _I)),
    _Method(
        "correlation",
        re.compile(r"\bcorrelat\w*|\bpearson\b|\bspearman\b", _I),
        re.compile(r"\bcorr\s*\(|correl|pearson|spearman", _I),
    ),
    _Method(
        "full scan",
        re.compile(
            r"\b(?:scann?ed|checked|went through|looked (?:at|through)|reviewed|examined|read)\s+"
            r"(?:through\s+)?(?:all|every|each)\s+(?:of\s+)?(?:the\s+)?(?:\w+\s+){0,2}?"
            r"(?:rows?|records?|lines?|entries)\b",
            _I,
        ),
        None,
    ),
)
_HEDGE = re.compile(
    r"\b(?:not|no|never|without|cannot|can't|couldn't|unable|instead of|rather than|would|could|"
    r"might|need|needs|require|requires|recommend|suggest|if you)\b|n't\b",
    _I,
)
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
_SQL = re.compile(r"\bselect\b[\s\S]*\bfrom\b", _I)
_LIMIT = re.compile(r"\blimit\s+\d+|\bfetch\s+first\b", _I)


def _args_text(call: Call) -> str:
    return json.dumps(call.args, ensure_ascii=False, default=str)


def _supported(method: _Method, calls: Sequence[Call]) -> str | None:
    for call in calls:
        if method.name == "python":
            if re.search("python", call.tool, _I):
                return call.tool
        elif method.name == "full scan":
            args = _args_text(call)
            if _SQL.search(args) and not _LIMIT.search(args):
                return call.tool
        elif method.trace is not None and method.trace.search(_args_text(call)):
            return call.tool
    return None


def _claims(answer: str, calls: Sequence[Call]) -> list[MethodClaim]:
    out = []
    for sentence in _SENTENCE.findall(answer):
        if _HEDGE.search(sentence):
            continue
        for method in METHODS:
            m = method.claim.search(sentence)
            if not m:
                continue
            evidence = _supported(method, calls)
            status: ClaimStatus = "supported" if evidence else "unsupported"
            out.append(MethodClaim(method.name, m.group(0), status, evidence))
    return out


# --- the check ------------------------------------------------------------------------------------


def check_turn(
    question: str,
    answer: str,
    calls: Sequence[Call],
    earlier: Sequence[Call] = (),
) -> Verdict:
    """The evidence verdict of one turn; `earlier` are the calls of the conversation's earlier
    turns, whose results the answer may also cite (their methods do not count for this turn)."""
    pool = [v for c in [*earlier, *calls] if c.result for v in result_numbers(c.result)]
    given = [n.value for n in _answer_numbers(question)]
    figures: list[Figure] = []
    table: list[tuple[float, str]] | None = None
    for n in _answer_numbers(answer):
        if any(abs(n.value - g) <= _EPS for g in given):
            continue
        hit = _cited(n, pool)
        if hit is not None:
            figures.append(Figure(n.text, n.value, "cited", f"{hit:g}"))
            continue
        if table is None:
            table = _derivations([*pool, *given])
        how = _derived(n, table)
        if how is not None:
            figures.append(Figure(n.text, n.value, "derived", how))
        else:
            figures.append(Figure(n.text, n.value, "untraced"))
    return Verdict(figures, _claims(answer, calls))


# --- the CLI over eval logs -----------------------------------------------------------------------


def load_questions(paths: Iterable[Path]) -> dict[str, list[str]]:
    """Each case's turn questions from eval sets in questions.yaml's shape (later files win)."""
    out: dict[str, list[str]] = {}
    for path in paths:
        for item in yaml.safe_load(path.read_text()).get("questions", []):
            turns = item.get("turns") or [item]
            out[item["id"]] = [t.get("question", "") for t in turns]
    return out


def _calls(turn: Mapping[str, Any]) -> list[Call]:
    return [
        Call(str(c.get("tool", "")), c.get("args") or {}, c.get("result"))
        for c in turn.get("calls") or []
    ]


@dataclass
class _Tally:
    checked: int = 0
    untraced: int = 0
    unsupported: int = 0
    right: int = 0
    right_untraced: int = 0
    right_unsupported: int = 0
    whole: int = 0
    whole_untraced: int = 0


@dataclass
class Summary:
    rows: int = 0
    turns: int = 0
    no_calls: int = 0
    no_results: int = 0
    no_question: int = 0
    groups: dict[tuple[str, str], _Tally] = field(default_factory=lambda: defaultdict(_Tally))
    examples: list[str] = field(default_factory=list)
    result_cap: int | None = None


def summarise(
    rows: Iterable[Mapping[str, Any]],
    questions: Mapping[str, list[str]],
    examples: int = 0,
    result_cap: int | None = None,
) -> Summary:
    s = Summary(result_cap=result_cap)
    for row in rows:
        s.rows += 1
        key = (str(row.get("arm") or row.get("setup") or "?"), str(row.get("model") or "?"))
        case = str(row.get("case", "?"))
        earlier: list[Call] = []
        for i, turn in enumerate(row.get("turns") or []):
            s.turns += 1
            calls = _calls(turn)
            if not calls:
                s.no_calls += 1
                continue
            if any(c.result is None for c in calls):
                s.no_results += 1
                earlier += calls
                continue
            question = turn.get("question")
            if question is None:
                asked = questions.get(case, [])
                question = asked[i] if i < len(asked) else None
            if question is None:
                s.no_question += 1
            answer = str(turn.get("answer") or turn.get("text") or "")
            verdict = check_turn(question or "", answer, calls, earlier)
            earlier += calls
            t = s.groups[key]
            t.checked += 1
            t.untraced += bool(verdict.untraced)
            t.unsupported += bool(verdict.unsupported)
            if turn.get("outcome") == "right":
                t.right += 1
                t.right_untraced += bool(verdict.untraced)
                t.right_unsupported += bool(verdict.unsupported)
            cut = result_cap is not None and any(len(c.result or "") >= result_cap for c in calls)
            if not cut:
                t.whole += 1
                t.whole_untraced += bool(verdict.untraced)
            if len(s.examples) < examples and (verdict.untraced or verdict.unsupported):
                figs = ", ".join(f.text for f in verdict.untraced)
                meths = ", ".join(f"{m.method} ({m.phrase!r})" for m in verdict.unsupported)
                s.examples.append(
                    f"{key[0]} | {key[1]} | {case} r{row.get('run', '?')} t{i + 1} | "
                    f"outcome {turn.get('outcome')} | untraced: {figs or '-'} | "
                    f"unsupported: {meths or '-'}{' | a result cut' if cut else ''}"
                )
    return s


def _share(part: int, whole: int) -> str:
    return f"{part / whole:.0%} ({part}/{whole})" if whole else "-"


def render(s: Summary) -> str:
    lines = [
        f"rows {s.rows}, turns {s.turns}: {sum(t.checked for t in s.groups.values())} checked, "
        f"{s.no_calls} made no call, {s.no_results} made calls whose results the log lacks "
        f"(not checkable); {s.no_question} checked without their question text",
        "",
        "| arm | model | checked | any untraced | any unsupported method "
        "| right | right: untraced | right: unsupported |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    if s.result_cap is not None:
        lines[2] += f" results whole (under {s.result_cap} chars) | whole: untraced |"
        lines[3] += "---:|---:|"
    for (arm, model), t in sorted(s.groups.items()):
        line = (
            f"| {arm} | {model} | {t.checked} | {_share(t.untraced, t.checked)} "
            f"| {_share(t.unsupported, t.checked)} | {t.right} "
            f"| {_share(t.right_untraced, t.right)} | {_share(t.right_unsupported, t.right)} |"
        )
        if s.result_cap is not None:
            line += f" {t.whole} | {_share(t.whole_untraced, t.whole)} |"
        lines.append(line)
    if s.examples:
        lines += ["", "Flagged turns:", *(f"- {e}" for e in s.examples)]
    return "\n".join(lines)


def _rows(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        with path.open() as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m semantic_agent.evidence", description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path, help="JSONL eval logs")
    parser.add_argument(
        "--questions",
        action="append",
        type=Path,
        default=[],
        help="an eval set (questions.yaml's shape) for turns whose log lacks the question",
    )
    parser.add_argument("--examples", type=int, default=0, help="list up to N flagged turns")
    parser.add_argument(
        "--result-cap",
        type=int,
        help="the length the log cut each result at: also report turns with whole results",
    )
    ns = parser.parse_args(argv)
    summary = summarise(_rows(ns.logs), load_questions(ns.questions), ns.examples, ns.result_cap)
    print(render(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
