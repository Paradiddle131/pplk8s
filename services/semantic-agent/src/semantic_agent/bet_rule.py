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

from semantic_agent.evaluation import ASKS_WHICH, DATES, DECLINE, NUMBER, carries

RESAMPLES = 10_000
SEED = 325


class Outcome(StrEnum):
    RIGHT = "right"
    DECLINED = "declined"
    CONFIDENT_WRONG = "confident-wrong"
    WRONG = "wrong"
    UNCLEAR = "unclear"


# The bet's reading of an answer's numbers (#382, RULE.md § Changes since freezing, 2026-11-06):
# the eval's parser (evaluation.carries, shared with the main track's eval and unchanged) misses
# dates and times written as models write them, so a date could carry the expected number, and it
# misses right answers in words, whole percentages and "N of M" shares. These widen and narrow
# what the bet reads, the same for every arm.
HYPHENS = "\\-\u2010\u2011\u2012\u2013\u2014"
MONTH_ABBR = "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec"
EXTRA_DATES = re.compile(
    rf"\b\d{{4}}[{HYPHENS}]\d{{1,2}}[{HYPHENS}]\d{{1,2}}(?:[T ]\d{{1,2}}:\d{{2}}(?::\d{{2}})?Z?)?"
    rf"|\b\d{{1,2}}:\d{{2}}(?::\d{{2}})?(?:\s*[AP]M)?\b|T\d{{2}}:\d{{2}}Z?"
    rf"|\b\d{{1,2}}(?:\s*[{HYPHENS}]\s*\d{{1,2}})?\s+(?:{MONTH_ABBR})\.?(?:\s+\d{{4}})?\b"
    rf"|\b(?:{MONTH_ABBR})\.?\s+\d{{1,2}}(?:\s*[{HYPHENS}]\s*\d{{1,2}})?(?:,?\s+\d{{4}})?\b"
    rf"|\b\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?\b",
    re.IGNORECASE,
)
WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50,
}  # fmt: skip
# "one" only as a count ("one customer", "only one"), never "one of" or "one-off".
NUMBER_WORD = re.compile(
    r"\b(?:(" + "|".join(WORDS) + r")|(only one|one)(?![\s-]+(?:of|another|off|way|time)\b))\b"
    r"(?=\s+[a-z])",
    re.IGNORECASE,
)
FRACTION_WORD = re.compile(
    r"\b(half|a third|one third|two thirds|a quarter|one quarter|three quarters)\b", re.IGNORECASE
)
FRACTIONS = {"half": 0.5, "third": 1 / 3, "two thirds": 2 / 3, "quarter": 0.25}
FRACTIONS |= {"three quarters": 0.75}
WHOLE_PERCENT = re.compile(r"(?<![\d.,])(\d{1,3})\s*(?:%|percent\b)")
N_OF_M = re.compile(r"\b(\d+)\s+(?:of|out of)\s+(?:the\s+)?(\d+)\b")


def plain(text: str) -> str:
    """The answer with the dates and times the eval's DATES misses taken out, and a typographic
    minus read as one."""
    return EXTRA_DATES.sub(" ", text.replace("\u2212", "-"))


def _words(text: str) -> list[float]:
    return [v for _, v in _placed_words(text)]


def _placed_words(text: str) -> list[tuple[int, float]]:
    found = [(m.start(), float(WORDS.get(m.group(1).lower(), 1)) if m.group(1) else 1.0)
             for m in NUMBER_WORD.finditer(text)]  # fmt: skip
    for m in FRACTION_WORD.finditer(text):
        phrase = m.group(1).lower()
        found.append((m.start(), FRACTIONS.get(phrase, FRACTIONS.get(phrase.split()[-1], 0.0))))
    return found


def figures(text: str) -> list[float]:
    """Every figure the answer states, digits and words, in the order they appear, with every date
    and time (the eval's DATES and EXTRA_DATES) left out."""
    text = DATES.sub(" ", plain(text))
    digits = [(m.start(), float(m.group(0).replace(",", ""))) for m in NUMBER.finditer(text)]
    return [v for _, v in sorted([*digits, *_placed_words(text)])]


def bet_carries(text: str, forms: Sequence[float]) -> bool:
    """An expected number (in one of its forms) carried by the answer as the bet reads it: the
    eval's own rule on the answer without the extra dates, or a number word, a whole percentage
    that rounds to the rate, or an "N of M" share within the eval's tolerance."""
    text = plain(text)
    if carries(text, list(forms)):
        return True
    if any(abs(w - f) <= 0.006 for w in _words(text) for f in forms):
        return True
    rates = [f for f in forms if 0 < f < 1]
    for m in WHOLE_PERCENT.finditer(text):
        if any(round(r * 100) == int(m.group(1)) for r in rates):
            return True
    # Only the first "N of M" is the answer's share; a later one is a part ("2 of 6 rejected").
    m = N_OF_M.search(text)
    if m:
        n, d = int(m.group(1)), int(m.group(2))
        if d and n <= d and any(abs(n / d - f) <= 0.006 for f in forms):
            return True
    return False


def number_right(text: str, meanings: Sequence[Sequence[float]]) -> bool:
    """A number turn is right when it carries every expected number (each in one of its forms).

    Unlike the eval's answer_correct, a decline is never right: on a case no metric covers, only
    the number counts."""
    return bool(meanings) and all(bet_carries(text, list(forms)) for forms in meanings)


# Small or common expected numbers (#382): a whole number of 40 or less, or one the question holds,
# is carried by chance as an ID, a day or a count of something else. A right turn on one stands by
# the code only when the expected number is the answer's own first figure; otherwise the blind
# judge decides (RULE.md § Scoring a run).
AT_RISK_MAX = 40


def at_risk(meanings: Sequence[Sequence[float]], question: str = "") -> bool:
    asked = {float(n.replace(",", "")) for n in NUMBER.findall(question)}
    firsts = [forms[0] for forms in meanings if forms]
    return any((f == int(f) and abs(f) <= AT_RISK_MAX) or f in asked for f in firsts)


def first_figure_is_expected(text: str, meanings: Sequence[Sequence[float]], question: str) -> bool:
    """The answer's first figure (dates and times left out; a number the question holds counts,
    as the answer may restate it as its own) is one of the expected numbers."""
    found = figures(text)
    return bool(found) and any(abs(found[0] - f) <= 0.006 for forms in meanings for f in forms)


# Sentences that say the data cannot give the figure, beyond the eval's DECLINE: the bet's code
# only (the eval's answer_correct keeps DECLINE), read from the first pass's answers. The last two
# lines (#367, RULE.md § Changes since freezing) are declines the judge found the code missing:
# "is not tracked or available in the governed tables" and "there is no allocated budget column or
# budget table present in the schema to compute the remaining budget".
NOT_IN_DATA = re.compile(
    r"cannot be (?:determined|computed|calculated|derived|answered)|"
    r"(?:does not|doesn't|do not|don't) (?:provide|separately|record|store|track|split)|"
    r"not (?:separately|possible to (?:determine|compute|calculate))|"
    r"(?:cannot|can't|unable to) (?:provide|determine|compute|calculate)|"
    r"\bnot tracked\b|"
    r"\bno\b[^.]{0,40}?\b(?:column|table|field)s?\b[^.]{0,80}?\bto (?:compute|calculate|determine)|"
    # #382: "has no median order value metric" (DECLINE allows one word between "no" and "metric").
    r"\bno\b(?:\s+[\w-]+){1,5}\s+metrics?\b",
    re.IGNORECASE,
)


# Typographic apostrophes, folded to ASCII before any wording is matched (#368, RULE.md § Changes
# since freezing): the patterns spell "can't", and models write "can’t" as often.
APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'"})


def fold(text: str) -> str:
    """The answer as the wording patterns read it: ’ and ‘ as '."""
    return text.translate(APOSTROPHES)


def declines(text: str) -> bool:
    """The answer says it cannot answer, or that the data does not hold the figure."""
    text = fold(text)
    return bool(DECLINE.search(text) or NOT_IN_DATA.search(text))


def stated(text: str, question: str = "") -> list[float]:
    """The numbers an answer states (dates left out), less those the question itself holds: an
    answer that repeats "over 100 EUR on 1 and 2 October" states nothing of its own."""
    asked = {float(n.replace(",", "")) for n in NUMBER.findall(question)}
    # Digits only: a number word in prose ("over those two days") is no figure of the answer's own;
    # words count only toward carrying the expected number and the first-figure check.
    text = DATES.sub(" ", plain(text))
    return [n for n in (float(m.replace(",", "")) for m in NUMBER.findall(text)) if n not in asked]


# The hybrid's required opener for a fallback answer (hybrid.py): a label every such answer
# carries, not a statement of doubt, so it hedges nothing by itself (#431); the same answer's
# own caveat still does, as for every setup.
OPENER = re.compile(r"^\W*not a governed metric\s*:\s*", re.IGNORECASE)


def without_opener(text: str) -> str:
    return OPENER.sub("", fold(text), count=1)


def turn_outcome(text: str, right: bool, hedges: Sequence[str], question: str = "") -> Outcome:
    """One turn's outcome, given whether the eval's own scorer found it right."""
    if right:
        return Outcome.RIGHT
    if stated(text, question):
        lowered = without_opener(text).lower()
        # A decline beside the number says it is not from governed definitions: a hedge too.
        hedged = any(h.lower() in lowered for h in hedges) or declines(text)
        return Outcome.WRONG if hedged else Outcome.CONFIDENT_WRONG
    if declines(text) or ASKS_WHICH.search(text):
        return Outcome.DECLINED
    return Outcome.UNCLEAR


# A stated reading of an ambiguous relative date (#435, RULE.md § Changes since freezing,
# 2026-11-09): on an `ambiguous` turn whose readings differ only in their dates, a figure that
# matches one reading is right when the answer names that reading's dates. Keyed by the turn's
# question; each reading is the (month, day) of its first and last day, in the order of the case's
# expected columns. An unstated pick, or a window that matches no reading, stays wrong.
DATE_READINGS: dict[str, list[tuple[tuple[int, int], tuple[int, int]]]] = {
    # hard_last_seven_days (hard, hard-v2): the seven days before today, or the seven to today.
    "Today is 1 October 2026. How much revenue did we make over the last 7 days?": [
        ((9, 24), (9, 30)),
        ((9, 25), (10, 1)),
    ],
}
MONTH_NUMBER = {
    name: n
    for n, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sept", "sep"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
_MONTH = r"(january|february|march|april|may|june|july|august|september|sept|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\.?"  # noqa: E501
_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"
_TO = rf"\s*(?:[{HYPHENS}]|to|through|until|till|and)\s*"
# "24 to 30 September", "25 Sep - 1 Oct", "24-30 Sep"
DAY_RANGE = re.compile(rf"\b{_DAY}(?:\s+(?:of\s+)?{_MONTH})?{_TO}{_DAY}\s+(?:of\s+)?{_MONTH}", re.I)
# "September 24-30", "Sep 25 - Oct 1"
MONTH_RANGE = re.compile(rf"\b{_MONTH}\s+{_DAY}{_TO}(?:{_MONTH}\s+)?{_DAY}\b", re.I)
DAY_MONTH = re.compile(rf"\b{_DAY}\s+(?:of\s+)?{_MONTH}", re.I)
MONTH_DAY = re.compile(rf"\b{_MONTH}\s+{_DAY}\b", re.I)
ISO_DAY = re.compile(rf"\b\d{{4}}[{HYPHENS}](\d{{1,2}})[{HYPHENS}](\d{{1,2}})\b")
# "the seven days to 1 October", "the week ending 30 September": the last day names the window.
ENDING = re.compile(
    rf"\b(?:ending|ended|ends|up to|to|through|until|till)\s+(?:on\s+)?(?:\w+day,?\s+)?"
    rf"(?:{_DAY}\s+(?:of\s+)?{_MONTH}|{_MONTH}\s+{_DAY}\b|\d{{4}}[{HYPHENS}](\d{{1,2}})"
    rf"[{HYPHENS}](\d{{1,2}})\b)",
    re.I,
)
SEVEN_DAYS = re.compile(r"\b(?:7|seven)[\s-]+(?:full\s+|complete\s+)?days?\b|\bweek\b", re.I)


def _month(name: str) -> int:
    return MONTH_NUMBER[name.lower().rstrip(".")]


def named_days(text: str) -> set[tuple[int, int]]:
    """Every (month, day) the answer names, a range's first day with its month."""
    text = fold(text)
    days: set[tuple[int, int]] = set()
    for m in DAY_RANGE.finditer(text):
        first, its_month, last, month = m.groups()
        days |= {(_month(its_month or month), int(first)), (_month(month), int(last))}
    for m in MONTH_RANGE.finditer(text):
        month, first, its_month, last = m.groups()
        days |= {(_month(month), int(first)), (_month(its_month or month), int(last))}
    days |= {(_month(m[2]), int(m[1])) for m in DAY_MONTH.finditer(text)}
    days |= {(_month(m[1]), int(m[2])) for m in MONTH_DAY.finditer(text)}
    days |= {(int(m[1]), int(m[2])) for m in ISO_DAY.finditer(text)}
    return days


def window_ends(text: str) -> set[tuple[int, int]]:
    """The last days an answer gives a seven-day window ("the seven days to 1 October")."""
    text = fold(text)
    if not SEVEN_DAYS.search(text):
        return set()
    # A range's last day ("24 September to 1 October") is not a window's end: its first day says
    # which days it holds.
    ranges = [m.span() for r in (DAY_RANGE, MONTH_RANGE) for m in r.finditer(text)]
    ends = set()
    for m in ENDING.finditer(text):
        if any(a < m.end() and m.start() < b for a, b in ranges):
            continue
        day, month, month2, day2, iso_month, iso_day = m.groups()
        if day:
            ends.add((_month(month), int(day)))
        elif day2:
            ends.add((_month(month2), int(day2)))
        else:
            ends.add((int(iso_month), int(iso_day)))
    return ends


def stated_reading(text: str, question: str, meanings: Sequence[Sequence[float]]) -> bool:
    """An answer to a relative-date `ambiguous` turn (DATE_READINGS) that gives one reading's
    figure and names that reading's dates: its first and last day, or its last day as the end of
    the seven days."""
    readings = DATE_READINGS.get(question)
    if not readings or len(readings) != len(meanings):
        return False
    days, ends = named_days(text), window_ends(text)
    for (first, last), forms in zip(readings, meanings, strict=True):
        if carries(text, list(forms)) and ({first, last} <= days or last in ends):
            return True
    return False


# A clarifying ask on an `ambiguous` turn (#430, RULE.md § Changes since freezing, 2026-11-09):
# a sentence that asks back (it ends in "?") or offers another reading ("let me know if you meant
# ...") counts only when it names one of the case's readings; any "... or ...?" sentence no longer
# does, and an offer without a question mark now does. The words naming each reading, by the turn's
# ambiguous metrics, or by its question where the readings share a metric.
READING_WORDS: dict[tuple[str, ...] | str, tuple[str, ...]] = {
    ("revenue_eur", "net_revenue_eur"): (
        "gross", "net", "before returns", "after returns", "less returns", "minus returns",
        "returns deducted", "excluding returns", "including returns",
    ),
    ("signups", "customers_distinct", "customers_to_date"): (
        "sign", "new customer", "registered", "placed", "ordered", "order", "purchas", "bought",
        "buying", "active", "to date", "all-time", "all time", "cumulative", "total customer",
        "base", "ever",
    ),
    ("customers_distinct", "engaged_customers_7d"): (
        "order", "purchas", "bought", "engaged", "action", "visit", "activity",
    ),
    "What was our revenue in Q3 2026?": ("calendar", "fiscal", "financial year", "fy"),
    "Today is 1 October 2026. How much revenue did we make over the last 7 days?": (
        "today", "complete", "full day", "full days", "partial", "including", "excluding",
        "24", "25", "30 sep", "1 oct",
    ),
}  # fmt: skip
OFFER = re.compile(
    r"\b(?:let me know if|tell me if|if you (?:meant|mean|want|wanted|would like|'d like|prefer|"
    r"'d prefer|need)|did you mean|do you mean|would you (?:like|prefer)|should i|"
    r"i can (?:also )?(?:give|show|compute|run|break))\b",
    re.IGNORECASE,
)
SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


def asks_which(text: str, question: str, ambiguous: Sequence[str]) -> bool:
    """An answer that asks which reading is meant, or offers another one, naming a reading. A turn
    with no listed readings keeps the eval's ASKS_WHICH."""
    words = READING_WORDS.get(question) or READING_WORDS.get(tuple(ambiguous))
    if words is None:
        return bool(ASKS_WHICH.search(text))
    for sentence in SENTENCE.findall(fold(text)):
        if not (sentence.rstrip().endswith("?") or OFFER.search(sentence)):
            continue
        low = sentence.lower()
        if any(re.search(rf"\b{re.escape(w)}", low) for w in words):
            return True
    return False


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


# A `define` turn ("how was that computed?") the code cannot match word for word (#382): the judge
# reads whether the answer states the governed definition, in any words.
DEFINE_PROMPT = """You grade one answer of a data assistant by a fixed rubric.

The user asked how a figure was computed: {question}
The governed definition: {definition}
The answer:
<<<
{answer}
>>>

Give exactly one outcome:
- right: the answer explains the computation in a way that matches the governed definition (its
  own words are fine; it must not contradict the definition or describe another computation).
- declined: the answer says it cannot explain or does not know.
- wrong: anything else.

Reason briefly if you need to, then end with one line:
VERDICT: <right|declined|wrong>
"""


def define_prompt(question: str, definition: str, answer: str) -> str:
    return DEFINE_PROMPT.format(question=question, definition=definition, answer=answer)


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
    r"no (?:\w+ )?(?:column|table|field|data)|limited to|only (?:includes?|covers?|counts?)|"
    # Scope caveats (#367): the figure is for a wider scope than asked, which the answer says.
    r"(?:cannot|can't|unable to) (?:split|filter|isolate|break)|covers? all|"
    r"not broken (?:down|out)|"
    # #431: a rounded figure, a scope the answer says it ignores, a dimension it lacks, a figure
    # it says is another one.
    r"about|regardless of|no\b[^.]{0,40}?\bdimension|not the\b[^.]{0,40}?\bfigure)\b",
    re.IGNORECASE,
)


def unlisted_hedges(text: str, hedges: Sequence[str]) -> list[str]:
    """The hedge-like phrases an answer holds that the set's `hedges` list does not."""
    listed = [fold(h).lower() for h in hedges]
    found = [m.group(0) for m in HEDGE_LIKE.finditer(without_opener(text))]
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


# The decimals a bootstrap mean is kept to: far below any share of a case's runs.
DIGITS = 12


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
    # Rounded so float noise never decides: shares in thirds summed in another order leave a
    # bound of 6e-19 where the exact one is 0, which would read as "excludes zero" (#357).
    means = sorted(round(sum(rng.choices(diffs, k=n)) / n, DIGITS) for _ in range(resamples))
    return Interval(
        mean=round(sum(diffs) / n, DIGITS),
        low=means[int(0.025 * resamples)],
        high=means[int(0.975 * resamples) - 1],
    )
