"""The semantic bet's scoring rule (docs/research/semantic-bet/RULE.md), as pure functions.

A turn's outcome is right, declined, confident-wrong or wrong; the code leaves to a blind judge
the answers it cannot decide (unclear, counted as wrong until judged). The judge's prompt and how
its two verdicts combine are here too; asking the judge (a model) is bet_eval.py's. A run of a
case is right when every turn is, confident-wrong when any turn is. An arm's accuracy and
confident-wrong rate are means over cases of the share of its k runs with that outcome; two arms
compare by the paired percentile bootstrap of their per-case differences. Nothing here calls a
model or a warehouse, and nothing changes how evals/questions.yaml's eval is scored.
"""

from __future__ import annotations

import hashlib
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
    r"not (?:separately|possible to (?:determine|compute|calculate))|"
    r"(?:cannot|can't|unable to) (?:provide|determine|compute|calculate)",
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


# RULE.md § Scoring a run: the blind judge sees the question, the expected number and the answer,
# never the arm, and gives one of the four outcomes under the rule's own definitions.
JUDGE_PROMPT = """You grade one answer of a data assistant to a user's question by a fixed rubric.

The question: {question}
The expected number: {expected}
The answer:
<<<
{answer}
>>>

Give exactly one outcome:
- right: the answer carries the expected number (rounding aside; a rate may be a percentage).
- declined: the answer gives no number and says it cannot answer, that the data or no definition
  covers it, or asks the user a question back.
- confident-wrong: the answer gives a number other than the expected one, with no statement that
  it is uncertain, partial, an estimate or not from governed definitions.
- wrong: anything else (another number with such a statement, or no number and no decline).

Reason briefly if you need to, then end with one line:
VERDICT: <right|declined|confident-wrong|wrong>
"""
VERDICT = re.compile(r"VERDICT:\W*(right|declined|confident-wrong|wrong)\b", re.IGNORECASE)


def _number(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def judge_prompt(question: str, meanings: Sequence[Sequence[float]], answer: str) -> str:
    """The judge's prompt for one turn: every expected number in its first form (a rate also as
    its percentage)."""
    shown = []
    for forms in meanings:
        number = _number(forms[0])
        shown.append(f"{number} ({_number(forms[1])}%)" if len(forms) > 1 else number)
    expected = ", ".join(shown) or "none (the question asks for no number)"
    return JUDGE_PROMPT.format(question=question, expected=expected, answer=answer)


def parse_verdict(text: str) -> Outcome | None:
    """The judge's verdict: its last VERDICT line, or None when it gave none."""
    found = VERDICT.findall(text)
    return Outcome(found[-1].lower()) if found else None


def two_verdicts(first: Outcome | None, second: Outcome | None) -> Outcome:
    """RULE.md: two equal verdicts stand; two different ones (or a missing one) leave it unclear."""
    if first is None or first is not second:
        return Outcome.UNCLEAR
    return first


# RULE.md's second judge case (#366): a hedge phrased outside the set's `hedges` list. The code
# cannot tell such a hedge from a confident wrong number, so every confident-wrong turn holding one
# of these hedge-like phrases goes to the judge. The list is broad on purpose (a false match costs
# two judge requests, a missed one leaves a hedged answer confident-wrong): uncertainty words,
# assumptions, scope notes and "the data does not hold it" phrasings, read from the logs' answers.
HEDGE_LIKE = re.compile(
    r"\b(?:approx(?:imately|\.)?|roughly|around|estimat\w*|may|might|could|likely|possibly|"
    r"perhaps|probably|appears?|seems?|assum\w*|not sure|uncertain\w*|unclear|partial\w*|"
    r"incomplete|caveats?|note that|please note|for reference|based on|treated as|taken as|"
    r"interpret\w*|proxy|depending|if you|not (?:tracked|available|recorded|stored|present)|"
    r"no (?:\w+ )?(?:column|table|field|data)|limited to|only (?:includes?|covers?|counts?))\b",
    re.IGNORECASE,
)


def unlisted_hedges(text: str, hedges: Sequence[str]) -> list[str]:
    """The hedge-like phrases an answer holds that the set's `hedges` list does not."""
    listed = [h.lower() for h in hedges]
    found = [m.group(0) for m in HEDGE_LIKE.finditer(text)]
    return [f for f in found if not any(f.lower() in h or h in f.lower() for h in listed)]


def hedge_verdicts(first: Outcome | None, second: Outcome | None) -> Outcome:
    """Two verdicts on a confident-wrong turn with an unlisted hedge: the code already found its
    number outside tolerance, so the judge decides only whether it is hedged. Equal verdicts of
    wrong or confident-wrong stand; declined is a decline beside the number, so hedged: wrong;
    right contradicts the parsed number, and different verdicts disagree: both unclear."""
    if first is None or first is not second or first is Outcome.RIGHT:
        return Outcome.UNCLEAR
    return Outcome.WRONG if first is Outcome.DECLINED else first


def answer_hash(text: str) -> str:
    """What a cached verdict is keyed on besides the turn: a changed answer is judged again."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


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
