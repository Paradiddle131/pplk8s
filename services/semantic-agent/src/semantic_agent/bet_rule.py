"""The semantic bet's scoring rule (docs/research/semantic-bet/RULE.md), as pure functions.

A turn's outcome is right, declined, confident-wrong or wrong; the code leaves to a blind judge
the answers it cannot decide (unclear, counted as wrong until judged). A run of a case is right when
every turn is, confident-wrong when any turn is. An arm's accuracy and confident-wrong rate are
means over cases of the share of its k runs with that outcome; two arms compare by the paired
percentile bootstrap of their per-case differences. Nothing here calls a model or a warehouse,
and nothing changes how evals/questions.yaml's eval is scored.
"""

from __future__ import annotations

import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from semantic_agent.evaluation import ASKS_WHICH, DECLINE, NUMBER, carries, numbers_in

RESAMPLES = 10_000
SEED = 325


class Outcome(StrEnum):
    RIGHT = "right"
    DECLINED = "declined"
    CONFIDENT_WRONG = "confident-wrong"
    WRONG = "wrong"
    UNCLEAR = "unclear"


def number_right(text: str, meanings: Sequence[Sequence[float]]) -> bool:
    """A number turn is right when it carries every expected number (each in one of its forms).

    Unlike the eval's answer_correct, a decline is never right: on a case no metric covers, only
    the number counts."""
    return bool(meanings) and all(carries(text, list(forms)) for forms in meanings)


# Sentences that say the data cannot give the figure, beyond the eval's DECLINE: the bet's code
# only (the eval's answer_correct keeps DECLINE), read from the first pass's answers.
NOT_IN_DATA = re.compile(
    r"cannot be (?:determined|computed|calculated|derived|answered)|"
    r"(?:does not|doesn't|do not|don't) (?:provide|separately|record|store|track|split)|"
    r"not (?:separately|possible to (?:determine|compute|calculate))",
    re.IGNORECASE,
)


def declines(text: str) -> bool:
    """The answer says it cannot answer, or that the data does not hold the figure."""
    return bool(DECLINE.search(text) or NOT_IN_DATA.search(text))


def stated(text: str, question: str = "") -> list[float]:
    """The numbers an answer states (dates left out), less those the question itself holds: an
    answer that repeats "over 100 EUR on 1 and 2 October" states nothing of its own."""
    asked = {float(n.replace(",", "")) for n in NUMBER.findall(question)}
    return [n for n in numbers_in(text) if n not in asked]


def turn_outcome(text: str, right: bool, hedges: Sequence[str], question: str = "") -> Outcome:
    """One turn's outcome, given whether the eval's own scorer found it right."""
    if right:
        return Outcome.RIGHT
    if stated(text, question):
        lowered = text.lower()
        # A decline beside the number says it is not from governed definitions: a hedge too.
        hedged = any(h.lower() in lowered for h in hedges) or declines(text)
        return Outcome.WRONG if hedged else Outcome.CONFIDENT_WRONG
    if declines(text) or ASKS_WHICH.search(text):
        return Outcome.DECLINED
    return Outcome.UNCLEAR


def run_outcome(turns: Sequence[Outcome]) -> Outcome:
    """A run of a case over its turns: confident-wrong wins, then right needs every turn right."""
    if Outcome.CONFIDENT_WRONG in turns:
        return Outcome.CONFIDENT_WRONG
    if all(t is Outcome.RIGHT for t in turns):
        return Outcome.RIGHT
    if Outcome.WRONG in turns:
        return Outcome.WRONG
    if Outcome.UNCLEAR in turns:
        return Outcome.UNCLEAR
    return Outcome.DECLINED


@dataclass(frozen=True)
class ArmScore:
    """An arm's numbers on one model: the two that decide and the ones reported beside them."""

    accuracy: float
    confident_wrong: float
    pass_k: float
    groups: dict[str, float]
    right: dict[str, float]
    wrong_confidently: dict[str, float]
    unclear: list[str]


def arm_score(
    runs: Mapping[str, Sequence[Outcome]], groups: Mapping[str, Sequence[str]]
) -> ArmScore:
    """Score an arm from each case's run outcomes (the same k runs for every case)."""
    if len({len(r) for r in runs.values()}) != 1:
        raise ValueError("every case needs the same number of runs")
    right = {c: sum(o is Outcome.RIGHT for o in r) / len(r) for c, r in runs.items()}
    confident = {c: sum(o is Outcome.CONFIDENT_WRONG for o in r) / len(r) for c, r in runs.items()}
    names = sorted({g for c in runs for g in groups[c]})
    by_group = {}
    for name in names:
        members = [right[c] for c in runs if name in groups[c]]
        by_group[name] = sum(members) / len(members)
    return ArmScore(
        accuracy=sum(right.values()) / len(right),
        confident_wrong=sum(confident.values()) / len(confident),
        pass_k=sum(v == 1.0 for v in right.values()) / len(right),
        groups=by_group,
        right=right,
        wrong_confidently=confident,
        unclear=[c for c, r in runs.items() if Outcome.UNCLEAR in r],
    )


@dataclass(frozen=True)
class Interval:
    """The mean of B minus A over cases and its percentile bootstrap 95% interval."""

    mean: float
    low: float
    high: float

    @property
    def differs(self) -> bool:
        return self.low > 0 or self.high < 0


def paired_interval(
    a: Mapping[str, float], b: Mapping[str, float], resamples: int = RESAMPLES, seed: int = SEED
) -> Interval:
    """Paired by case: resample cases with replacement and take the 2.5th and 97.5th percentiles."""
    if set(a) != set(b):
        raise ValueError("both arms must be scored on the same cases")
    cases = sorted(a)
    diffs = [b[c] - a[c] for c in cases]
    n = len(diffs)
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(diffs, k=n)) / n for _ in range(resamples))
    return Interval(
        mean=sum(diffs) / n,
        low=means[int(0.025 * resamples)],
        high=means[int(0.975 * resamples) - 1],
    )
