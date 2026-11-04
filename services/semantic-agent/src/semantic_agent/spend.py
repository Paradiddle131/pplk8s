"""Claude spend (#361): every call's `usage` priced, a pass's dollar budget, and the spend ledger.

The bet's Claude passes run on the owner's $100.00 of credits. model.py builds the Claude model;
every call it makes goes through `METER`: `check` refuses a call the pass's budget cannot cover
(`BudgetSpent`, so the call is never sent), `record` prices the call's usage and appends it to the
calls log, `failure` keeps a refused or failed call. A runner opens a pass with `METER.start`, marks
each case-run with `begin_case`/`end_case` (whose usage it logs beside the run's outcome), asks
`room_for_case` before the next case, and closes the pass with `finish_pass`, which appends the
pass's row to the ledger with the anomaly checks the owner asked for (#361, 2026-11-03).

Prices are USD per million tokens from Anthropic's pricing page,
https://platform.claude.com/docs/en/about-claude/pricing (read 2026-11-03): base input, 5-minute
cache writes, cache hits, output; Claude Haiku 5.5 bills a prompt over 100,000 tokens (input, cache
reads and writes together) at its long-context prices. Fable is never priced, so never allowed.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import re
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FINDINGS = Path(__file__).resolve().parents[4] / "docs" / "research" / "semantic-bet" / "findings"
# Every Claude call, one JSON line each; the ledger's totals are read from it.
CALLS_LOG = FINDINGS / "2026-11-03-361-claude-calls.jsonl"
LEDGER = FINDINGS / "2026-11-03-361-claude-spend.md"
PROBE_LOG = FINDINGS / "2026-11-03-361-cost-probe.jsonl"
CREDITS = 100.0
# The owner's alarm line: the running total past this is an anomaly. The stop is $88.00 of real
# spend (docs/agents/autopilot-semantic-bet.md § The completion plan; owner 2026-11-04 at 81% of the
# month's limit: "plan accordingly no need to hit the literal 100"), and this log misses the $3.0704
# the night's lost container billed (the Console's $85.37 left, 2026-11-04).
UNLOGGED = 3.0704
STOP = 88.0
ALARM = STOP - UNLOGGED
# A call (or case-run) whose tokens are over this many times the probe's per-case median.
TOKEN_FACTOR = 3.0
# Before a pass has priced a call on a model, the next call is estimated at this many uncached
# input and output tokens (the plan's assumption, #361: about 12k input a call).
PRIOR_INPUT, PRIOR_OUTPUT = 12_000, 2_000
# Spelled in two parts so a grep of the repository for the key prefix finds no key.
KEY_SHAPE = re.compile("sk-" + r"ant-[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input: float
    cache_write: float  # 5-minute TTL, the only one the runner writes
    cache_read: float
    output: float


@dataclass(frozen=True)
class Tier:
    base: Price
    long: Price | None = None
    long_above: int | None = None  # prompt tokens past which `long` applies


PRICES: dict[str, Tier] = {
    "claude-haiku-5-5": Tier(
        Price(0.10, 0.125, 0.01, 0.50), long=Price(0.50, 0.625, 0.05, 2.50), long_above=100_000
    ),
    "claude-sonnet-5-5": Tier(Price(2.00, 2.50, 0.10, 10.00)),
    "claude-opus-5-5": Tier(Price(4.00, 5.00, 0.20, 20.00)),
}


@dataclass(frozen=True)
class Usage:
    """Tokens and dollars of one call or a sum of calls. `input` is the uncached input only."""

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    calls: int = 0
    dollars: float = 0.0

    @property
    def tokens(self) -> int:
        return self.input + self.output + self.cache_read + self.cache_write

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            *(getattr(self, f.name) + getattr(other, f.name) for f in dataclasses.fields(self))
        )

    def as_dict(self) -> dict[str, Any]:
        return {**dataclasses.asdict(self), "dollars": round(self.dollars, 6)}


def total(usages: Iterable[Usage]) -> Usage:
    return sum(usages, Usage())


def usage_of(meta: Any) -> Usage:
    """One call's tokens from ADK's usage metadata as LiteLLM fills it for Anthropic: the prompt
    count holds the uncached input, the cache reads and the cache writes together."""
    read = meta.cached_content_token_count or 0
    write = getattr(meta, "cache_creation_input_tokens", None) or 0
    prompt = meta.prompt_token_count or 0
    return Usage(
        input=max(0, prompt - read - write),
        output=meta.candidates_token_count or 0,
        cache_read=read,
        cache_write=write,
        calls=1,
    )


def priced(model: str, usage: Usage) -> Usage:
    """One call's usage with its dollars, at the model's published prices."""
    tier = PRICES[model]
    prompt = usage.input + usage.cache_read + usage.cache_write
    price = tier.long if tier.long and tier.long_above and prompt > tier.long_above else tier.base
    dollars = (
        usage.input * price.input
        + usage.cache_write * price.cache_write
        + usage.cache_read * price.cache_read
        + usage.output * price.output
    ) / 1_000_000
    return dataclasses.replace(usage, dollars=dollars)


def redact(text: str) -> str:
    """An error's text with anything shaped like an Anthropic key cut out."""
    return KEY_SHAPE.sub("[redacted]", text)


class BudgetSpent(RuntimeError):
    """The pass's dollar budget cannot cover the next call: it is never sent."""


def now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Meter:
    """The calls of this process, the open pass and its budget."""

    log: Path | None = CALLS_LOG
    label: str = ""
    budget: float | None = None
    calls: list[tuple[str, Usage]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    cases: list[tuple[str, Usage]] = field(default_factory=list)  # the pass's case-runs
    context: dict[str, Any] = field(default_factory=dict)
    first: int = 0  # index of the pass's first call
    first_failure: int = 0
    stopped: bool = False  # a call was refused for the budget

    def start(self, label: str, budget: float | None, log: Path | None = CALLS_LOG) -> None:
        self.label, self.budget, self.log = label, budget, log
        self.first, self.first_failure = len(self.calls), len(self.failures)
        self.cases, self.context, self.stopped = [], {}, False

    @property
    def pass_calls(self) -> list[tuple[str, Usage]]:
        return self.calls[self.first :]

    @property
    def pass_failures(self) -> list[dict[str, Any]]:
        return self.failures[self.first_failure :]

    @property
    def spent(self) -> float:
        return sum(u.dollars for _, u in self.pass_calls)

    def estimate(self, model: str) -> float:
        """The next call's dollars: the dearest call this pass made on the model, else the prior."""
        seen = [u.dollars for m, u in self.pass_calls if m == model]
        if seen:
            return max(seen)
        return priced(model, Usage(input=PRIOR_INPUT, output=PRIOR_OUTPUT)).dollars

    def check(self, model: str) -> None:
        """Refuse the next call when it would take the pass past its budget."""
        if self.budget is None:
            return
        estimate = self.estimate(model)
        if self.spent + estimate > self.budget:
            self.stopped = True
            raise BudgetSpent(
                f"pass {self.label!r} spent ${self.spent:.4f} of ${self.budget:.2f}; "
                f"the next call is estimated at ${estimate:.4f}"
            )

    def record(self, model: str, usage: Usage) -> Usage:
        usage = priced(model, usage)
        self.calls.append((model, usage))
        if self.log is not None:
            row = {"at": now(), "pass": self.label, "model": model, **self.context}
            with self.log.open("a") as out:
                out.write(json.dumps({**row, **usage.as_dict()}) + "\n")
        return usage

    def failure(self, model: str, failure: Any) -> None:
        self.failures.append(
            {
                "at": now(),
                "model": model,
                "kind": failure.kind,
                "message": redact(failure.message)[:300],
            }
        )

    def mark(self) -> int:
        return len(self.calls)

    def since(self, mark: int) -> Usage:
        return total(u for _, u in self.calls[mark:])

    def begin_case(self, model: str, **context: Any) -> int:
        """Start a case-run on `model`: its calls are logged with `context` (arm, run, case)."""
        self.context = {"case_model": model, **context}
        return self.mark()

    def end_case(self, mark: int) -> Usage:
        usage = self.since(mark)
        if usage.calls:
            self.cases.append((self.context.get("case_model", ""), usage))
        self.context = {}
        return usage

    def room_for_case(self) -> bool:
        """Whether the budget covers another case-run as dear as the dearest one this pass."""
        if self.budget is None:
            return True
        if self.stopped:
            return False
        dearest = max((u.dollars for _, u in self.cases), default=0.0)
        return self.spent + dearest <= self.budget


METER = Meter()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def probe_medians(entries: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Per model, the median tokens of a case-run in the cost probe's log."""
    by_model: dict[str, list[int]] = {}
    for e in entries:
        if e.get("usage"):
            u = e["usage"]
            by_model.setdefault(e["model"], []).append(
                u["input"] + u["output"] + u["cache_read"] + u["cache_write"]
            )
    return {m: statistics.median(t) for m, t in by_model.items()}


def anomalies(
    meter: Meter,
    budget: float | None,
    running: float,
    medians: Mapping[str, float],
    cases: Sequence[tuple[str, Usage]] = (),
) -> list[str]:
    """The owner's checks on the pass just run (#361, 2026-11-03), one line each that fired."""
    found = []
    spent = meter.spent
    if budget is not None and spent > budget:
        found.append(f"over budget: ${spent:.4f} of ${budget:.2f}")
    for model, usage in meter.pass_calls:
        median = medians.get(model)
        if median and usage.tokens > TOKEN_FACTOR * median:
            found.append(
                f"a call of {usage.tokens} tokens on {model}, over {TOKEN_FACTOR:g} x the "
                f"probe's per-case median ({median:g})"
            )
    for model, usage in cases:
        median = medians.get(model)
        if median and usage.tokens > TOKEN_FACTOR * median:
            found.append(
                f"a case-run of {usage.tokens} tokens on {model}, over {TOKEN_FACTOR:g} x the "
                f"probe's per-case median ({median:g})"
            )
    for f in meter.pass_failures:
        if f["kind"] == "billing":
            found.append(f"billing error on {f['model']}: {f['message']}")
        elif f["kind"] in ("rate_limit", "daily_quota"):
            found.append(f"429 on {f['model']}: {f['message']}")
        elif f["kind"] == "auth":
            found.append(f"key refused on {f['model']}: {f['message']}")
    if running > ALARM:
        found.append(f"running total ${running:.4f} is past ${ALARM:.2f}")
    return found


def finish_pass(
    meter: Meter = METER,
    ledger: Path = LEDGER,
    calls_log: Path = CALLS_LOG,
    probe_log: Path = PROBE_LOG,
    note: str = "",
) -> list[str]:
    """Append the pass's row to the ledger, with the running total read from the calls log, and
    return the anomaly checks that fired (also written in the row)."""
    usage = total(u for _, u in meter.pass_calls)
    running = sum(row["dollars"] for row in read_jsonl(calls_log))
    medians = probe_medians(read_jsonl(probe_log))
    found = anomalies(meter, meter.budget, running, medians, meter.cases)
    models = ", ".join(sorted({m for m, _ in meter.pass_calls})) or "none"
    budget = f"${meter.budget:.2f}" if meter.budget is not None else "none"
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")
    cells = [
        stamp,
        meter.label + (f" ({note})" if note else ""),
        models,
        str(usage.calls),
        str(usage.input),
        str(usage.output),
        str(usage.cache_read),
        str(usage.cache_write),
        f"${usage.dollars:.4f}",
        budget,
        f"${running:.4f}",
        "; ".join(found) or "none",
    ]
    with ledger.open("a") as out:
        out.write("| " + " | ".join(cells) + " |\n")
    return found
