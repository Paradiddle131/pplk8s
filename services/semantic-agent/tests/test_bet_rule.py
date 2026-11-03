"""The semantic bet's scoring rule (docs/research/semantic-bet/RULE.md), on scripted answers."""

import pytest

from semantic_agent import bet_rule
from semantic_agent.bet_rule import Outcome, arm_score, paired_interval, run_outcome, turn_outcome
from semantic_agent.evaluation import as_expected

HEDGES = ["approximately", "roughly", "an estimate", "not a defined metric"]
REVENUE = as_expected(1850.34)


def test_a_turn_with_the_number_is_right():
    text = "Revenue over 1 and 2 October 2026 was €1,850.34."
    assert turn_outcome(text, bet_rule.number_right(text, [REVENUE]), HEDGES) is Outcome.RIGHT


def test_a_rate_as_a_percentage_is_right():
    text = "16.7% of orders were cancelled."
    assert bet_rule.number_right(text, [as_expected(1 / 6)])


def test_an_unhedged_wrong_number_is_confident_wrong():
    text = "Revenue over 1 and 2 October 2026 was €2,148.83."
    outcome = turn_outcome(text, bet_rule.number_right(text, [REVENUE]), HEDGES)
    assert outcome is Outcome.CONFIDENT_WRONG


def test_a_hedged_wrong_number_is_wrong_not_confident():
    text = "Roughly €2,148.83, though cancelled orders may be in it."
    assert turn_outcome(text, False, HEDGES) is Outcome.WRONG
    text = "€2,148.83; revenue is not a defined metric here, so I summed every order."
    assert turn_outcome(text, False, HEDGES) is Outcome.WRONG


def test_a_wrong_number_beside_a_decline_is_hedged():
    text = "No metric covers the median, but summing every order gives 2,148.83."
    assert turn_outcome(text, False, HEDGES) is Outcome.WRONG


def test_a_decline_without_a_number_is_declined():
    text = "I can't answer that: the semantic layer doesn't define a median order value."
    assert turn_outcome(text, False, HEDGES) is Outcome.DECLINED
    assert turn_outcome("Do you mean gross sales or net sales?", False, HEDGES) is Outcome.DECLINED


def test_a_decline_on_an_uncovered_case_is_not_right():
    # RULE.md: on an uncovered case only the number is right; the scorer never counts a decline.
    text = "No metric covers the median order value, so I cannot answer."
    assert not bet_rule.number_right(text, [as_expected(45.0)])
    assert turn_outcome(text, False, HEDGES) is Outcome.DECLINED


def test_no_number_and_no_decline_goes_to_the_judge():
    text = "Revenue was strong over those two days, led by Germany."
    assert turn_outcome(text, False, HEDGES) is Outcome.UNCLEAR


def test_dates_alone_are_not_a_number():
    text = "On 1 October 2026 the data was not available."
    assert turn_outcome(text, False, HEDGES) is Outcome.DECLINED


@pytest.mark.parametrize(
    ("turns", "expected"),
    [
        ([Outcome.RIGHT, Outcome.RIGHT], Outcome.RIGHT),
        ([Outcome.RIGHT, Outcome.CONFIDENT_WRONG], Outcome.CONFIDENT_WRONG),
        ([Outcome.DECLINED, Outcome.CONFIDENT_WRONG], Outcome.CONFIDENT_WRONG),
        ([Outcome.RIGHT, Outcome.DECLINED], Outcome.DECLINED),
        ([Outcome.RIGHT, Outcome.UNCLEAR], Outcome.UNCLEAR),
        ([Outcome.WRONG, Outcome.DECLINED], Outcome.WRONG),
    ],
)
def test_a_run_is_right_only_when_every_turn_is(turns, expected):
    assert run_outcome(turns) is expected


def test_an_arms_scores_over_k_runs_and_groups():
    runs = {
        "a": [Outcome.RIGHT, Outcome.RIGHT, Outcome.RIGHT],
        "b": [Outcome.RIGHT, Outcome.CONFIDENT_WRONG, Outcome.UNCLEAR],
        "c": [Outcome.DECLINED, Outcome.DECLINED, Outcome.WRONG],
    }
    groups = {"a": ["covered", "trap"], "b": ["covered"], "c": ["uncovered"]}
    score = arm_score(runs, groups)
    assert score.accuracy == pytest.approx((1 + 1 / 3 + 0) / 3)
    assert score.confident_wrong == pytest.approx((0 + 1 / 3 + 0) / 3)
    assert score.pass_k == pytest.approx(1 / 3)
    assert score.groups == {"covered": pytest.approx(2 / 3), "trap": 1.0, "uncovered": 0.0}
    assert score.unclear == ["b"]
    assert score.right["b"] == pytest.approx(1 / 3)


def test_an_arm_needs_the_same_runs_per_case():
    with pytest.raises(ValueError, match="runs"):
        arm_score({"a": [Outcome.RIGHT] * 3, "b": [Outcome.RIGHT] * 2}, {"a": [], "b": []})


def test_a_clear_gap_excludes_zero_and_no_gap_includes_it():
    cases = [f"q{i}" for i in range(60)]
    a = {c: 0.0 if i % 2 else 1.0 for i, c in enumerate(cases)}
    better = {c: 1.0 for c in cases}
    gap = paired_interval(a, better)
    assert gap.mean == pytest.approx(0.5)
    assert gap.low > 0 and gap.differs
    same = {c: a[cases[(i + 2) % 60]] for i, c in enumerate(cases)}
    tie = paired_interval(a, same)
    assert tie.low <= 0 <= tie.high and not tie.differs


def test_the_interval_is_deterministic_and_paired_on_the_same_cases():
    a = {f"q{i}": i % 3 / 2 for i in range(30)}
    b = {f"q{i}": (i + 1) % 3 / 2 for i in range(30)}
    assert paired_interval(a, b) == paired_interval(a, b)
    with pytest.raises(ValueError, match="same cases"):
        paired_interval(a, {**b, "extra": 1.0})
