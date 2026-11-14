"""Count which frozen questions the generated Toolbox tools can answer, by their shapes (offline, by hand).

What it measures: for every case of the frozen set (services/semantic-agent/evals/semantic_bet.yaml), whether an
agent that can only call the tools answers it, under two tool sets:
- `saved`: the seven tools probes/330_tools.yaml serves, one per saved query (probes/329_bet_shaped.sql), each
  `(start_date, end_date)` returning that saved query's metrics by its fixed group-bys;
- `per_metric`: a counterfactual generator, one tool per metric returning it per day or over the whole range
  (MetricFlow's query with only `metric_time`), with no other dimension or filter.
Verdicts, read by hand from each case's question and expected SQL against the tools' columns (2026-11-03):
- `exact`: one call, then reading a value, adding an additive column or picking a row answers it;
- `derived`: the agent's own arithmetic over the rows of at most two calls answers it (a ratio of sums, a growth,
  a share): the number can be right, but the formula is the agent's, not a governed one;
- `out`: no call answers it; the reason names what is missing.
`per_metric` is computed, not judged: `exact` when the case's metrics exist (a covered case) and it needs no
dimension or filter besides dates (`NEEDS`) and no explanation of a definition; `derived` for the uncovered cases
whose arithmetic needs only dates (`PER_METRIC_DERIVED`); otherwise `out`.

Run from the repo root (offline):  uv run --with pyyaml python docs/research/semantic-bet/probes/330_shape_coverage.py
Env: none. Live: no.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
FROZEN = ROOT / "services/semantic-agent/evals/semantic_bet.yaml"

# The `saved` verdict and its tool or reason, per case, in the set's order.
SAVED: dict[str, tuple[str, str]] = {
    "revenue_total": ("exact", "daily_sales, sum"),
    "revenue_one_day": ("exact", "daily_sales"),
    "revenue_best_day": ("exact", "daily_sales, max row"),
    "net_revenue_one_day": ("exact", "net_sales_daily"),
    "net_revenue_total": ("exact", "net_sales_daily, sum"),
    "orders_one_day": ("exact", "daily_sales"),
    "cancelled_total": ("exact", "daily_sales, sum"),
    "cancellation_rate": ("derived", "daily_sales, cancelled / orders"),
    "active_customers": ("exact", "daily_sales, one day"),
    "returns_amount": ("exact", "net_sales_daily, sum"),
    "returns_one_day": ("exact", "net_sales_daily"),
    "shipped_orders": ("exact", "orders_by_status, a wide range"),
    "damaged_returns": (
        "exact",
        "damaged_returns_daily or returns_by_reason, a wide range",
    ),
    "revenue_germany": ("exact", "sales_by_country_daily"),
    "net_revenue_germany": ("out", "dimension: net revenue has no country"),
    "revenue_signup_cohort": ("out", "dimension: signup month"),
    "orders_over_100": ("out", "filter: order amount"),
    "best_weekday_revenue": ("exact", "daily_sales, sum by weekday"),
    "top_campaigns_by_spend": ("out", "dimension: campaign (spend is by channel)"),
    "signups_september": ("out", "metric: signups"),
    "customers_to_date": ("out", "metric: customers_to_date"),
    "signup_to_first_order_rate": ("out", "metric: signup_to_first_order_rate"),
    "repeat_revenue_share": ("out", "metric: repeat_revenue_share"),
    "return_rate_september": ("out", "metric: return_rate (returns by order date)"),
    "damaged_return_share": (
        "out",
        "metric: damaged_return_share (returns by order date)",
    ),
    "average_order_value": ("derived", "daily_sales, revenue / (orders - cancelled)"),
    "median_order_value": ("out", "no metric: a median"),
    "revenue_fiscal_q3": (
        "exact",
        "daily_sales, sum; the fiscal calendar is in no tool",
    ),
    "budget_left_end_of_september": ("out", "metric: remaining_budget_eur"),
    "amsterdam_temperature": ("out", "no metric: weather"),
    "cost_per_booking_total": (
        "derived",
        "channel_performance, sum spend / sum bookings over channels",
    ),
    "cost_per_lead_search": ("exact", "channel_performance, the search row"),
    "lead_to_booking_rate": (
        "out",
        "metric: lead_to_booking_rate (bookings by lead cohort)",
    ),
    "page_views_one_day": ("out", "metric: customer_actions"),
    "engaged_customers_week": ("out", "metric: engaged_customers_7d"),
    "monthly_active_customers": ("out", "metric: engaged_customers_28d"),
    "view_to_cart_rate": ("out", "metric: view_to_cart_rate"),
    "outreach_messages_sent": ("out", "metric: messages_sent"),
    "outreach_reply_rate": ("out", "metric: reply_rate"),
    "partners_engaged_one_day": ("out", "metric: partners_engaged"),
    "candidates_in_interview_as_of": ("out", "metric: candidates_in_stage"),
    "time_to_hire": ("out", "metric: time_to_hire_days"),
    "calls_about_returns": ("out", "metric: calls_labelled"),
    "objection_rate": ("out", "metric: objection_rate"),
    "revenue_wow_growth": ("derived", "daily_sales over two weeks, a growth"),
    "bookings_wow_growth": ("derived", "channel_performance, two calls, a growth"),
    "leads_wow_growth": ("derived", "channel_performance, two calls, a growth"),
    "revenue_mtd": ("exact", "daily_sales, sum"),
    "leads_mtd": ("exact", "channel_performance, sum over channels"),
    "followup_by_country": ("exact", "daily_sales, then sales_by_country_daily"),
    "followup_day_before": ("exact", "daily_sales"),
    "followup_switch_metric": ("exact", "daily_sales, then net_sales_daily"),
    "followup_how_computed": (
        "out",
        "explanation: Toolbox hides the statement and the function's SQL",
    ),
    "followup_rate_how_computed": (
        "derived",
        "daily_sales; the agent explains its own division",
    ),
    "ambiguous_sales": ("exact", "daily_sales, then net_sales_daily"),
    "ambiguous_customers": (
        "out",
        "metric: signups; customers_distinct by day does not add up to a month",
    ),
    "planted_campaign_top_spend": ("out", "dimension: campaign"),
    "planted_campaign_least_spend": ("out", "dimension: campaign"),
    "planted_top_customer": ("out", "dimension: customer"),
    "bet_cancellation_rate_period": (
        "derived",
        "daily_sales, sum cancelled / sum orders",
    ),
    "bet_customers_september": (
        "out",
        "non-additive: customers_distinct by day does not add up to a month",
    ),
    "bet_top_country_september": ("exact", "sales_by_country_daily, sum by country"),
    "bet_weekday_most_orders": ("exact", "daily_sales, sum by weekday"),
    "bet_ad_spend_september": ("exact", "channel_performance, sum over channels"),
    "bet_channel_lowest_cpl": ("exact", "channel_performance, min row"),
    "bet_lead_to_booking_september": ("out", "metric: lead_to_booking_rate"),
    "bet_top_call_topic": ("out", "metric: calls_labelled"),
    "bet_topic_objection_rate": ("out", "metric: objection_rate"),
    "bet_top_campaign_spend": ("out", "dimension: campaign"),
    "bet_top_return_reason_share": ("derived", "returns_by_reason, max amount / sum"),
    "bet_avg_days_to_return": ("out", "no metric: a duration"),
    "bet_median_session_minutes": ("out", "no metric: a median"),
    "bet_peak_page_view_hour": ("out", "no metric: an hour of day"),
    "bet_median_reply_hours": ("out", "no metric: a median"),
    "bet_applicants_reaching_interview": ("out", "no metric: a stage share"),
    "bet_median_days_to_hire": ("out", "no metric: a median"),
    "bet_istanbul_warmer": ("out", "no metric: weather"),
    "bet_ad_spend_per_order": (
        "derived",
        "channel_performance and daily_sales, spend / (orders - cancelled)",
    ),
    "bet_delivery_calls_per_100_shipped": (
        "out",
        "no metric: calls by topic per shipped order",
    ),
    "bet_median_order_september": ("out", "no metric: a median"),
    "bet_p90_order": ("out", "no metric: a percentile"),
    "bet_customers_over_three_orders": ("out", "no metric: customers by order count"),
    "bet_median_signup_to_first_order": ("out", "no metric: a median"),
    "bet_aov_old_vs_new_customers": ("out", "no metric: a cohort difference"),
    "bet_median_days_to_return": ("out", "no metric: a median"),
    "bet_damaged_vs_wrong_size": (
        "derived",
        "returns_by_reason, amount / count per reason, a difference",
    ),
    "bet_median_days_lead_to_booking": ("out", "no metric: a median"),
    "bet_weekday_avg_spend": (
        "out",
        "dimension: day (spend is by channel over the range)",
    ),
    "bet_cart_to_checkout_minutes": ("out", "no metric: a median duration"),
    "bet_most_email_opens": ("out", "no metric: per customer"),
    "bet_peak_checkout_hour": ("out", "no metric: an hour of day"),
    "bet_p75_reply_hours": ("out", "no metric: a percentile"),
    "bet_median_days_to_interview": ("out", "no metric: a median"),
    "bet_wetter_day_nl_orders": ("out", "no metric: weather"),
    "bet_revenue_per_ad_euro": (
        "derived",
        "daily_sales and channel_performance, revenue / spend",
    ),
    "bet_sessions_per_order": ("out", "no metric: sessions per order"),
}

# Covered cases that need a dimension or filter besides dates, or a definition explained: `out` per metric too.
NEEDS: dict[str, str] = {
    "net_revenue_germany": "country",
    "revenue_germany": "country",
    "revenue_signup_cohort": "signup month",
    "orders_over_100": "order amount",
    "shipped_orders": "order status",
    "damaged_returns": "return reason",
    "top_campaigns_by_spend": "campaign",
    "cost_per_lead_search": "channel",
    "page_views_one_day": "action type",
    "candidates_in_interview_as_of": "stage",
    "calls_about_returns": "call topic",
    "followup_by_country": "country",
    "followup_how_computed": "an explanation of the definition",
    "planted_campaign_top_spend": "campaign",
    "planted_campaign_least_spend": "campaign",
    "planted_top_customer": "customer",
    "bet_top_country_september": "country",
    "bet_channel_lowest_cpl": "channel",
    "bet_top_call_topic": "call topic",
    "bet_topic_objection_rate": "call topic",
    "bet_top_campaign_spend": "campaign",
}

# Uncovered cases the agent's arithmetic answers from per-metric tools with dates only.
PER_METRIC_DERIVED = {"bet_ad_spend_per_order", "bet_revenue_per_ad_euro"}


def per_metric(case_id: str, groups: list[str]) -> tuple[str, str]:
    if case_id in PER_METRIC_DERIVED:
        return "derived", "two metrics' tools, a ratio"
    if "covered" not in groups:
        return "out", "no metric"
    if case_id in NEEDS:
        return "out", f"needs {NEEDS[case_id]}"
    return "exact", "the metric's own tool"


def main() -> int:
    frozen = yaml.safe_load(FROZEN.read_text())
    ids = [case["id"] for case in frozen["questions"]]
    if sorted(ids) != sorted(SAVED) or any(n not in ids for n in NEEDS):
        print("the verdicts do not match the frozen set's cases", file=sys.stderr)
        return 1
    groups = frozen["groups"]
    names = ["covered", "uncovered", "trap", "distractor", "conversation", "planted"]
    table: dict[str, collections.Counter] = {}
    for case_id in ids:
        saved = SAVED[case_id][0]
        metric = per_metric(case_id, groups[case_id])[0]
        for group in ["all", *groups[case_id]]:
            table.setdefault(group, collections.Counter()).update(
                [f"saved {saved}", f"per_metric {metric}"]
            )
    print(
        f"{len(ids)} cases; columns: the `saved` tools (exact, derived, out), then `per_metric` (exact, derived, out)"
    )
    print(
        "| Group | Cases | saved exact | saved derived | saved out | per-metric exact | per-metric derived | per-metric out |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for group in ["all", *names]:
        c = table.get(group, collections.Counter())
        total = c["saved exact"] + c["saved derived"] + c["saved out"]
        cells = [
            c[k]
            for k in (
                "saved exact",
                "saved derived",
                "saved out",
                "per_metric exact",
                "per_metric derived",
                "per_metric out",
            )
        ]
        print(f"| {group} | {total} | " + " | ".join(str(x) for x in cells) + " |")
    reasons = collections.Counter(
        SAVED[i][1].split(":")[0] for i in ids if SAVED[i][0] == "out"
    )
    print("saved out, by reason:", dict(reasons.most_common()))
    tools = collections.Counter(
        tool.strip()
        for i in ids
        if SAVED[i][0] != "out"
        for tool in SAVED[i][1]
        .split(";")[0]
        .replace(" or ", ",")
        .replace(" and ", ",")
        .split(",")
        if tool.strip()
        in {
            "daily_sales",
            "net_sales_daily",
            "sales_by_country_daily",
            "orders_by_status",
            "returns_by_reason",
            "damaged_returns_daily",
            "channel_performance",
        }
    )
    print("saved tools used by exact or derived cases:", dict(tools.most_common()))
    covered_metric_exact = [
        i for i in ids if per_metric(i, groups[i])[0] != "out" and SAVED[i][0] == "out"
    ]
    print(
        f"per_metric answers where saved is out: {len(covered_metric_exact)}: {', '.join(covered_metric_exact)}"
    )
    lost = [
        i for i in ids if SAVED[i][0] != "out" and per_metric(i, groups[i])[0] == "out"
    ]
    print(f"saved answers that per_metric loses: {len(lost)}: {', '.join(lost)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
