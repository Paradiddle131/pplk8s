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


# Answers verbatim from the first pass's log (docs/research/semantic-bet/eval-local.jsonl), which
# the parser first called confident-wrong.
ECHOED = (
    "How many orders of more than 100 EUR were placed on 1 and 2 October 2026?",
    "The available tables only contain daily sales aggregates (e.g., `orders_total`, "
    "`revenue_eur`) and no per‑order amount detail, so the number of individual orders above 100 "
    "EUR on 1–2 October 2026 cannot be determined from the warehouse.",
)
NOT_SEPARATE = (
    "How much did returns of damaged goods cost us?",
    "The tables do not separately identify returns of damaged goods. Total returns across all "
    "reasons cost 89.75 EUR from 2026-08-17 to 2026-10-10.",
)
NOT_PROVIDED = (
    "What was our net revenue from customers in Germany on 1 October 2026, after returns?",
    "On 1 October 2026, revenue for Germany (country code DE) was 379.75 EUR across 3 orders in "
    "exposed.sales_by_country_daily. However, the warehouse does not provide a country-level net "
    "revenue after returns (returns are only aggregated globally in exposed.net_sales_daily), so "
    "a Germany-specific after-returns net figure cannot be computed from the available tables.",
)


def test_numbers_the_question_holds_are_not_stated_by_the_answer():
    question, text = ECHOED
    assert bet_rule.stated(text, question) == []
    assert turn_outcome(text, False, HEDGES, question) is Outcome.DECLINED


# The custom-toolbox arm's answer, verbatim from a live run with the model's reasoning kept apart.
CANNOT_PROVIDE = (
    "How many distinct customers bought from us in September 2026?",
    "I cannot provide the total number of distinct customers for September 2026 because daily "
    "distinct customer counts are not additive across days (customers may purchase on multiple "
    "days), and no tool returns a period-level distinct customer total. Daily distinct customers "
    "ranged from 3 to 4 throughout",
)


@pytest.mark.parametrize("question, text", [NOT_SEPARATE, NOT_PROVIDED, CANNOT_PROVIDE])
def test_another_figure_beside_not_in_the_data_is_hedged(question, text):
    assert turn_outcome(text, False, HEDGES, question) is Outcome.WRONG


def test_a_plain_wrong_number_stays_confident_wrong_beside_the_questions_numbers():
    question = "What share of the orders placed in September 2026 were returned?"
    text = "0% of the 120 orders placed in September 2026 were returned."
    assert turn_outcome(text, False, HEDGES, question) is Outcome.CONFIDENT_WRONG


def test_the_judge_sees_the_question_the_expected_number_and_the_answer_never_the_arm():
    prompt = bet_rule.judge_prompt(
        "Share of orders cancelled?", [as_expected(1 / 6)], "Most orders went through."
    )
    assert "Share of orders cancelled?" in prompt and "Most orders went through." in prompt
    assert "0.1667 (16.6667%)" in prompt
    assert "native" not in prompt and "arm" not in prompt.lower()


@pytest.mark.parametrize(
    ("reply", "verdict"),
    [
        ("No number is given.\nVERDICT: wrong", Outcome.WRONG),
        ("VERDICT: **Confident-wrong**", Outcome.CONFIDENT_WRONG),
        ("Could be right. VERDICT: declined", Outcome.DECLINED),
        ("I think it is wrong.", None),
    ],
)
def test_the_judges_verdict_is_its_last_verdict_line(reply, verdict):
    assert bet_rule.parse_verdict(reply) is verdict


def test_two_equal_verdicts_stand_and_two_different_leave_the_turn_unclear():
    assert bet_rule.two_verdicts(Outcome.DECLINED, Outcome.DECLINED) is Outcome.DECLINED
    assert bet_rule.two_verdicts(Outcome.DECLINED, Outcome.WRONG) is Outcome.UNCLEAR
    assert bet_rule.two_verdicts(None, None) is Outcome.UNCLEAR


# #367: declines the blind judge found the code missing (findings/2026-11-03-366-unlisted-hedges.md)
# and the same "not tracked" wording in two answers the judge had to decide; verbatim from the logs.

# native-governed, bet_median_days_lead_to_booking, run 1: a figure beside it (30 days).
NOT_TRACKED = (
    "For leads that turned into a booking in September 2026, what was the median number of days "
    "from lead creation to booking?",
    "The requested metric (median number of days from lead creation to booking) is not "
    "tracked or available in the governed tables. The available governed metrics related "
    "to lead conversion include **lead-to-booking rate** (the share of leads that booked "
    "within 30 days of creation) in `governed.leads_by_period`, as well as daily counts "
    "of **leads** (`governed.leads_daily`) and **bookings** (`governed.bookings_daily`).",
)

# native-shaped, budget_left_end_of_september, run 3: total spend beside it.
NO_BUDGET_COLUMN = (
    "How much of our campaigns' budget was left at the end of September 2026?",
    "The available data records marketing **spend** (in `silver.ad_spend`), but there is "
    "no allocated **budget** column or budget table present in the schema to compute the "
    "remaining budget at the end of September 2026. For reference, the total ad spend "
    "across all campaigns through September 30, 2026 was **€9,165** (Search: €5,565, "
    "Social: €3,150, Email: €450).",
)

# native-shaped, outreach_reply_rate, run 3: no number.
NOT_TRACKED_OR_STORED = (
    "What share of the outreach messages we sent from 1 to 3 October 2026 got a reply?",
    "The available datasets only track online orders, customer profiles, product returns, "
    "ad spend, leads, and bookings. Outreach messages (and their corresponding replies) "
    "are not tracked or stored in the database.",
)

# native-shaped, candidates_in_interview_as_of, run 3: no number.
NOT_TRACKED_IN_DATABASE = (
    "How many candidates were in the interview stage on 4 October 2026?",
    "The available dataset contains information on e-commerce sales, orders, partner "
    "returns, customers, and marketing campaigns (spend, leads, bookings). Data regarding "
    "job candidates or hiring/interview stages is not tracked in the current database.",
)


@pytest.mark.parametrize("question, text", [NOT_TRACKED, NO_BUDGET_COLUMN])
def test_a_figure_beside_a_not_tracked_or_no_column_decline_is_hedged(question, text):
    assert bet_rule.declines(text)
    assert turn_outcome(text, False, HEDGES, question) is Outcome.WRONG


@pytest.mark.parametrize("question, text", [NOT_TRACKED_OR_STORED, NOT_TRACKED_IN_DATABASE])
def test_not_tracked_without_a_number_is_declined(question, text):
    assert turn_outcome(text, False, HEDGES, question) is Outcome.DECLINED


# #367: custom-lightdash's scope caveats (findings/2026-11-03-363-lightdash-numbers.md), verbatim:
# a figure for a wider scope than asked, saying so. The code cannot tell such a caveat from a plain
# statement, so they stay confident-wrong for the code and go to the judge as hedge-like.

# custom-lightdash, revenue_germany, run 1.
CANNOT_SPLIT = (
    "What was our revenue from customers in Germany on 1 October 2026?",
    "Total revenue on 1 October 2026 was €981.69 (non-cancelled orders only). The "
    "semantic layer cannot split revenue by country — country is not a dimension on the "
    "revenue explore (slv_orders), so a Germany‑only figure isn't available; the closest "
    "metrics are revenue_eur (total, no country split) and signups (country available, "
    "but no revenue).",
)

# custom-lightdash, net_revenue_germany, run 1.
COVERS_ALL = (
    "What was our net revenue from customers in Germany on 1 October 2026, after returns?",
    "Net revenue on 1 October 2026 was €956.94 (revenue €981.69 minus returns €24.75), "
    "covering that single day. The semantic layer cannot split revenue by customer "
    "country—country isn't a dimension on orders or returns—so this figure covers all "
    "countries, not Germany specifically.",
)

# custom-lightdash, candidates_in_interview_as_of, run 1.
CANNOT_FILTER = (
    "How many candidates were in the interview stage on 4 October 2026?",
    "I queried the `candidates_in_stage` metric in `slv_candidate_days` for 4 October "
    "2026, which returned **6 candidates** across all hiring stages on that day. However, "
    "the semantic layer does not expose a `candidate__stage` dimension on this explore, "
    "so I cannot filter the result to isolate candidates specifically in the interview "
    "stage. Metric definition used: *Candidates who had applied by the end of each day, "
    "counted per day; grouped by candidate__stage (or filtered on it) it is the number in "
    "each hiring stage at the end of that day, from the stage history.* Period covered: 4 "
    "October 2026.",
)


@pytest.mark.parametrize(
    ("answer", "phrases"),
    [
        (CANNOT_SPLIT, ["cannot split"]),
        (COVERS_ALL, ["cannot split", "covers all"]),
        (CANNOT_FILTER, ["cannot filter"]),
        (("", "Revenue is not broken down by country: 981.69 EUR in all."), ["not broken down"]),
    ],
)
def test_a_scope_caveat_is_a_hedge_like_phrase_for_the_judge(answer, phrases):
    question, text = answer
    assert bet_rule.unlisted_hedges(text, HEDGES) == phrases
    assert turn_outcome(text, False, HEDGES, question) is Outcome.CONFIDENT_WRONG


def test_a_plain_figure_for_a_wider_scope_has_no_hedge_like_phrase():
    assert bet_rule.unlisted_hedges("Total revenue on 1 October 2026 was €981.69.", HEDGES) == []


# #368: custom-lightdash, cost_per_lead_search, run 1, verbatim, with its typographic apostrophe.
CANT_ISOLATE = (
    "How much did a lead from search campaigns cost us in early October 2026?",
    "The semantic layer has no “cost per lead” metric, and neither ad spend nor leads are broken "
    "out by campaign channel, so I can’t isolate search‑campaign lead cost. The closest available "
    "metrics are: - **ad_spend_eur** – ad spend across campaigns, in EUR - **leads** – CRM leads "
    "created, on the day they were created If you can tell me which campaign IDs are the search "
    "campaigns, I can pull their spend and lead counts for early October 2026.",
)


def test_a_typographic_apostrophe_is_read_as_an_ascii_one():
    question, text = CANT_ISOLATE
    assert bet_rule.fold("can’t ‘x’") == "can't 'x'"
    # "can't isolate" is a scope caveat, not a decline wording: with no number the code still
    # leaves the answer to the judge, and beside a figure it sends it there as hedge-like.
    assert bet_rule.unlisted_hedges(text, HEDGES) == ["can't isolate", "If you"]
    assert turn_outcome(text, False, HEDGES, question) is Outcome.UNCLEAR
    figure = text.replace("lead cost.", "lead cost; all leads cost 12.40 EUR each.")
    assert turn_outcome(figure, False, HEDGES, question) is Outcome.CONFIDENT_WRONG
    assert "can't isolate" in bet_rule.unlisted_hedges(figure, HEDGES)


@pytest.mark.parametrize(
    ("text", "outcome"),
    [
        ("I can’t answer that.", Outcome.DECLINED),
        ("The warehouse doesn’t track replies.", Outcome.DECLINED),
        ("The warehouse doesn’t track replies; sent messages were 40.", Outcome.WRONG),
    ],
)
def test_declines_and_hedges_match_with_a_typographic_apostrophe(text, outcome):
    assert turn_outcome(text, False, HEDGES) is outcome


def test_float_noise_never_makes_an_interval_exclude_zero():
    """#357: native-context-bare against native-context, shares in thirds, read a low bound of
    5.8e-19 where the exact one is 0, and so "a difference"."""
    pairs = {
        (3, 3): 79,
        (0, 0): 8,
        (2, 3): 4,
        (1, 3): 1,
        (1, 0): 1,
        (0, 2): 1,
        (1, 2): 1,
        (3, 2): 1,
    }
    a, b = {}, {}
    for (x, y), k in pairs.items():
        for _ in range(k):
            case = f"c{len(a):02d}"
            a[case], b[case] = x / 3, y / 3
    gap = paired_interval(a, b)
    assert gap.low == 0 and not gap.differs


# #382: the bet reads numbers past the eval's parser, the same for every arm.
def test_number_words_whole_percentages_and_shares_carry_the_expected_number():
    assert bet_rule.number_right("Nine distinct customers bought on 2 October.", [[9.0]])
    assert bet_rule.number_right("About 33% of the leads booked.", [[1 / 3, 100 / 3]])
    assert bet_rule.number_right("5 of 30 orders were cancelled.", [[1 / 6, 100 / 6]])
    assert bet_rule.number_right("Half of the calls had an objection.", [[0.5, 50.0]])
    # "one of the campaigns" is not a count of one.
    assert not bet_rule.number_right("It was one of the campaigns that spent the most.", [[1.0]])


def test_a_date_or_time_written_as_models_write_it_carries_nothing():
    assert not bet_rule.number_right("Partners engaged on Oct 2, 2026: 1 partner", [[2.0]])
    assert not bet_rule.number_right("The checkout at 09:10 was the first.", [[10.0]])
    assert not bet_rule.number_right("Customers to date as of Sept 30: 28.", [[30.0]])
    assert not bet_rule.number_right("From Sep 21–27 the cost rose by 30.", [[27.0]])
    assert not bet_rule.number_right("On 2026‑09‑30 we had 12 customers.", [[30.0]])


def test_only_the_first_share_is_the_answers_share():
    text = "4 of 6 were still in the running; 2 of 6 had been rejected."
    assert not bet_rule.number_right(text, [[1 / 3, 100 / 3]])


def test_a_multi_word_no_metric_is_a_decline():
    assert bet_rule.declines(
        "The semantic layer has no median order value metric; the closest is 47."
    )


def test_a_small_expected_number_stands_only_as_the_answers_first_figure():
    assert bet_rule.at_risk([[9.0]]) and not bet_rule.at_risk([[114.39]])
    assert bet_rule.at_risk([[30.0]]) and bet_rule.at_risk([[2026.5]], "over 2026.5 EUR")
    question = "How many partners replied on 2 October 2026?"
    assert bet_rule.first_figure_is_expected(
        "2 partners replied on 2 October 2026.", [[2.0]], question
    )
    listed = "13 customers never ordered: 11, 13, 14, 16, 17."
    assert not bet_rule.first_figure_is_expected(listed, [[16.0]], "How many?")


SEVEN = "Today is 1 October 2026. How much revenue did we make over the last 7 days?"
SEVEN_MEANINGS = [[3360.75], [3800.44]]


@pytest.mark.parametrize(
    "answer",
    [
        "Revenue for the last 7 days, 24 to 30 September 2026, was €3,360.75.",
        "Revenue over the last 7 days (24–30 September 2026) was 3,360.75 EUR.",
        "Revenue was €3,800.44 over the last 7 days (25 September – 1 October 2026).",
        "I assumed 25 Sep–1 Oct: €3,800.44.",
        "Revenue (Sep 25 - Oct 1, 2026) was 3800.44 EUR.",
        "From 2026-09-24 to 2026-09-30 revenue was 3,360.75 EUR.",
        "Revenue in the seven days to 1 October was €3,800.44.",
        "The week ending 30 September brought €3,360.75.",
    ],
)
def test_one_relative_date_reading_with_its_dates_is_right(answer):
    """#435: a figure matching one reading of an ambiguous relative date is right when the
    answer names that reading's dates."""
    assert bet_rule.stated_reading(answer, SEVEN, SEVEN_MEANINGS)


@pytest.mark.parametrize(
    "answer",
    [
        "Revenue over the last 7 days was €3,800.44.",  # an unstated pick
        "Revenue over the last 7 days (24 September – 1 October 2026): €4,342.44.",  # 8 days
        "Revenue over the last 7 days (24 September to 1 October 2026) was €3,800.44.",
        "Revenue for 24 to 30 September 2026 was €3,800.44.",  # the other reading's figure
        "Revenue in the seven days to 1 October was €3,360.75.",
    ],
)
def test_an_unstated_pick_or_a_window_no_reading_holds_stays_wrong(answer):
    assert not bet_rule.stated_reading(answer, SEVEN, SEVEN_MEANINGS)


def test_a_stated_reading_counts_only_on_a_relative_date_case():
    other = "What were our sales on 1 October 2026?"
    assert not bet_rule.stated_reading(
        "Sales on 1 October 2026 were 868.65 EUR.", other, [[868.65], [800.0]]
    )


Q3 = "What was our revenue in Q3 2026?"


@pytest.mark.parametrize(
    "answer",
    [
        "Revenue was €17,656.25. Let me know if you meant fiscal Q3.",  # an offer, no "?"
        "Do you mean the calendar or the fiscal quarter?",
        "Revenue for fiscal Q3 was €19,793.59; if you meant calendar Q3, I can run that instead.",
    ],
)
def test_an_ask_or_an_offer_naming_a_reading_counts_as_asking(answer):
    """#430: asking back, or offering another reading, names one of the case's readings."""
    assert bet_rule.asks_which(answer, Q3, ["revenue_eur"])


@pytest.mark.parametrize(
    "answer",
    [
        "Revenue was €17,656.25. Do you want me to retry now, or wait?",  # names no reading
        "Revenue was €17,656.25. Anything else, or shall we stop here?",
        "Revenue was €17,656.25 for the fiscal quarter.",  # names a reading, asks nothing
    ],
)
def test_a_question_that_names_no_reading_is_not_asking(answer):
    assert not bet_rule.asks_which(answer, Q3, ["revenue_eur"])


def test_a_turn_without_listed_readings_keeps_the_evals_ask():
    assert bet_rule.asks_which("Which one, A or B?", "Some question?", ["a", "b", "c", "d"])
