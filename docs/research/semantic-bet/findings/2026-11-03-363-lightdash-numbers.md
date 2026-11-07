# Lightdash's numbers against MetricFlow's on data, and an ADK agent on its free query API (#363)

Question (Q9, follow-up of [#334](../../../../../../issues/334)): on data, do the 36 metrics open-source Lightdash translated from our MetricFlow project give MetricFlow's numbers, and how does an agent do that reaches the semantic layer only through Lightdash's free query API?
[#334's finding](2026-11-03-334-lightdash.md) compared compiled SQL only, on an empty warehouse.

## What was run

- Data: the agents' fixture in the Compose warehouse's `dbt_dev` (`DB=dbt_dev tests/e2e/agent-fixture.sh`, rebuilt by another lane at about 19:59Z under the exclusive warehouse lock; 217 orders), not `make dbt-build`'s `warehouse`.
  Why: `dbt_dev` is where the frozen set's expected numbers come from (`328_mcp_live.py`, `bet_eval.py`), so the arm's numbers and the match check read the same rows the scorer does.
- 2026-11-03T20:00Z, [`probes/334_lightdash.sh`](../probes/334_lightdash.sh) unchanged: `Translated 36 MetricFlow metric(s) into Lightdash metrics (skipped 20 unsupported …)`, the same 36 as #334.
- 20:13Z, [`probes/334_lightdash_server.sh`](../probes/334_lightdash_server.sh) with three new env vars (`LIGHTDASH_PORT=18363`, off the shared stack's 5433, 5434, 4480 and 8085; `DBT_DBNAME=dbt_dev`; `LIGHTDASH_WAREHOUSE_CATALOG=1`), `--keep`: `lightdash/lightdash:3.128.0`, no licence, `Deploy completed! 68 explores deployed.`, the MCP endpoint and AI-agent API still `422` as in #334.
  Two fixes the script needed to run queries, not only compile them: `sslmode: disable` in the project copy's profile (else every query failed with `The server does not support SSL connections`), and a `dbt parse` for `DBT_DBNAME`'s database (the manifest names it in every `FROM`).
  With the warehouse catalog the date columns become date dimensions with day to year grains; without it (#334's run) every column is a string, which a date range cannot filter.
- 20:15Z, [`probes/363_lightdash_numbers.py`](../probes/363_lightdash_numbers.py) under the shared warehouse lock: for each translated metric two fixed queries, both ways.
  - `total`: the metric with no dimension and no filter, over every row the fixture holds.
  - `by_day`: the metric by its own time dimension at day grain (MetricFlow's `metric_time__day`; Lightdash's `<model>_<agg_time_dimension>_day`), every day either side returns.
  - Lightdash through its free query API (`POST /api/v2/projects/<p>/query/metric-query`, then `GET …/query/<uuid>`); MetricFlow through the semantic agent's own tool path (`semantic_agent.metrics.run`, MetricFlow's engine on `dbt/` parsed for `dbt_dev`, the `agent_metrics` role).
  - Tolerance: a value matches within 1e-6 absolute or 1e-9 relative; a day one side gives as 0 and the other leaves out or returns as null (no qualifying row) is counted apart as zero-filled, not as a mismatch.
- 20:19Z to 20:29Z, the arm `custom-lightdash` ([`probes/363_lightdash_agent.py`](../probes/363_lightdash_agent.py)) on the frozen set through the bet's runner (`probes/328_mcp_live.py --agent 363_lightdash_agent.py --runs 3`), under the OpenRouter lock, two passes with `--requests 6` and `--requests 79 --minutes 8`, model `nvidia/nemotron-3.5-super-vl:free` through `semantic_agent/model.py`; runs log to [`eval-custom-lightdash.jsonl`](../eval-custom-lightdash.jsonl) and score in [`eval.md`](../eval.md).
  The agent: one ADK `FunctionTool`, `query_metrics(explore, metrics, dimensions, start_date, end_date, date_dimension, filters)`, which checks every name against the explores Lightdash serves, builds a Lightdash metric query (never SQL), runs it through the same free API and returns the rows (at most 200), each metric's description and the SQL Lightdash compiled; the instruction is the semantic agent's MetricFlow instruction cut to this tool, plus the 13 explores that hold a metric (their descriptions, metrics and dimensions, about 11 KB), read from Lightdash's API when the agent is built.
- 20:29Z: the Lightdash containers and network removed, and the four images deleted (Lightdash's is 15 GB unpacked; the disk was down to 6.8 GB free).
- The OpenRouter key endpoint shows no free-request count (`limit_remaining` is the paid $50 limit, unspent); the orchestrator's count was about 158 of 1,000 left at 20:12Z, so this session's budget was 85 (about 54%).

## Lightdash's numbers beside MetricFlow's (`measured`, 20:15Z)

35 matched, 1 mismatched, 0 not comparable, of 36.

| Metric | Type | Explore | Total, MetricFlow | Total, Lightdash | By day (days MF / LD) | Verdict |
|---|---|---|---|---|---|---|
| `acting_customers` | simple | `slv_customer_actions` | 10 | 10 | 4 / 4, all equal | matched |
| `ad_clicks` | simple | `slv_ad_spend` | 23,828 | 23,828 | 47 / 47, all equal | matched |
| `ad_spend_eur` | simple | `slv_ad_spend` | 9,555 | 9,555 | 47 / 47, all equal | matched |
| `applications` | simple | `slv_applications` | 6 | 6 | 5 / 5, all equal | matched |
| `average_order_value_eur` | ratio | `slv_orders` | 100.475 | 100.475 | 54 / 54, all equal | matched |
| `booking_value_eur` | simple | `slv_bookings` | 197,700 | 197,700 | 42 / 42, all equal | matched |
| `bookings` | simple | `slv_bookings` | 80 | 80 | 42 / 42, all equal | matched |
| `calls_labelled` | simple | `slv_call_signals` | 52 | 52 | 7 / 7, all equal | matched |
| `calls_with_objection` | simple | `slv_call_signals` | 24 | 24 | 7 / 7, all equal | matched |
| `cancellation_rate` | ratio | `slv_orders` | 0.0921659 | 0.0921659 | 17 / 54, all equal; 37 zero-filled by Lightdash | matched |
| `candidates_in_stage` | simple | `slv_candidate_days` | 6 | 6 | 10 / 10, all equal | matched |
| `cart_sessions` | simple | `slv_customer_actions` | 5 | 5 | 4 / 4, all equal | matched |
| `checkout_sessions` | simple | `slv_customer_actions` | 2 | 2 | 4 / 4, all equal | matched |
| `customer_actions` | simple | `slv_customer_actions` | 21 | 21 | 4 / 4, all equal | matched |
| `customers_distinct` | simple | `slv_orders` | 17 | 17 | 54 / 54, all equal | matched |
| `damaged_return_share` | ratio | `slv_returns` | 0.5 | 0.5 | 3 / 4, all equal; 1 zero-filled by Lightdash | matched |
| `hires` | simple | `slv_applications` | 2 | 2 | 2 / 3, all equal; 1 zero-filled by Lightdash | matched |
| `leads` | simple | `slv_leads` | 211 | 211 | 47 / 47, all equal | matched |
| `messages_replied` | simple | `slv_outreach_messages` | 4 | 4 | 4 / 4, all equal | matched |
| `messages_sent` | simple | `slv_outreach_messages` | 7 | 7 | 4 / 4, all equal | matched |
| `objection_rate` | ratio | `slv_call_signals` | 0.461538 | 0.461538 | 7 / 7, all equal | matched |
| `orders_cancelled` | simple | `slv_orders` | 20 | 20 | 17 / 54, all equal; 37 zero-filled by Lightdash | matched |
| `orders_total` | simple | `slv_orders` | 217 | 217 | 54 / 54, all equal | matched |
| `partners_engaged` | simple | `slv_outreach_replies` | 2 | 2 | 3 / 3, all equal | matched |
| `positive_calls` | simple | `slv_call_signals` | 18 | 18 | 7 / 7, all equal | matched |
| `positive_sentiment_share` | ratio | `slv_call_signals` | 0.346154 | 0.346154 | 7 / 7, all equal | matched |
| `remaining_budget_eur` | simple | `slv_campaign_budgets` | 10,010 | 370,835 | 47 / 47, all equal | **mismatched** |
| `replies` | simple | `slv_outreach_replies` | 5 | 5 | 3 / 3, all equal | matched |
| `reply_rate` | ratio | `slv_outreach_messages` | 0.571429 | 0.571429 | 4 / 4, all equal | matched |
| `returns_count` | simple | `slv_returns` | 6 | 6 | 4 / 4, all equal | matched |
| `returns_eur` | simple | `slv_returns` | 89.75 | 89.75 | 4 / 4, all equal | matched |
| `returns_on_order_date` | simple | `slv_returns` | 6 | 6 | 4 / 4, all equal | matched |
| `revenue_eur` | simple | `slv_orders` | 19,793.59 | 19,793.59 | 54 / 54, all equal | matched |
| `signups` | simple | `slv_customers` | 30 | 30 | 30 / 30, all equal | matched |
| `site_sessions` | simple | `slv_customer_actions` | 10 | 10 | 4 / 4, all equal | matched |
| `time_to_hire_days` | simple | `slv_applications` | 6.0833 | 6.0833 | 2 / 2, all equal | matched |

- **`remaining_budget_eur` is silently wrong over any range longer than a day.**
  MetricFlow's metric is semi-additive (`non_additive_dimension: {name: snapshot_date, window_choice: max, window_groupings: [campaign]}`: each campaign's last snapshot, added up over campaigns); Lightdash translated it to a plain `sum` of `remaining_eur` and dropped the non-additive dimension with no line in the compile or deploy log, while keeping the description that says "never a sum across days".
  By hand on `dbt_dev`: `sum(remaining_eur)` over every snapshot is 370,835.00, over each campaign's last snapshot 10,010.00; the two queries agree with Lightdash and MetricFlow respectively.
  By day it matches (one snapshot per campaign a day), so only a period total exposes it.
- Zero-filled days are a representation difference, not a number: on a day with orders but no cancelled order, Lightdash's `COUNT(CASE WHEN status = 'cancelled' …)` says 0 (and the rate 0), while MetricFlow applies the metric's filter as a `WHERE` and returns no row for that day (the rate null); `hires` by `hired_date` gets one Lightdash row for the null date (candidates not hired) at 0, which MetricFlow leaves out.
  Every figure both sides give is equal, so these count as matched.
- Each explore holds only its own model's columns (`slv_orders` has one table, no joins): MetricFlow's entity-joined dimensions (`customer__country` on orders, `candidate__stage` on candidate days, `campaign__channel` on spend and leads) have no Lightdash counterpart, so a by-country or by-stage question has no Lightdash query at all.
  That is not a number mismatch (the two fixed queries above use none of them), but it bounds what the arm can answer.

## The arm on the frozen set (`measured`, 20:19Z to 20:29Z)

- Tolerance check passed for 35 of 36 metrics, the miss named and explained, so the arm was built and scored as the issue says; `remaining_budget_eur`'s loss stays in the arm on purpose, as a team adopting Lightdash would have it.
- How far it got: run 1 of 41 of the 96 cases (the set's order, `revenue_total` to `candidates_in_interview_as_of`); the second pass stopped on its 8-minute bound, not its request budget; 77 model responses spent (both passes; the runner counts responses, so retries the model client made on a 429 are not in it); runs 2 and 3 not started, so k = 1, not the target k = 3.
- Scored by `bet_rule` (no blind judge yet), on the 41 cases every arm on this model reached (`eval.md`):

  | | `baseline` | `custom-metricflow` | `custom-lightdash` |
  |---|---|---|---|
  | Accuracy | 63.4% | 95.1% | 58.5% |
  | Confident-wrong | 14.6% | 0.0% | 17.1% |
  | `covered` (39) accuracy | 64.1% | 100.0% | 61.5% |
  | `trap` (8) accuracy | 50.0% | 100.0% | 50.0% |

  Outcomes: 24 right, 7 confident-wrong, 7 declined, 1 wrong, 2 unclear (`median_order_value` and `cost_per_lead_search` decline in words outside the rule's list).
  Paired by case on the same 41, percentile bootstrap 95% (10,000 resamples, seed 325, `bet_rule.paired_interval`), descriptive (RULE.md § The rule, 5; no managed arm runs on this model):
  `custom-lightdash` minus `custom-metricflow`: accuracy -0.366 [-0.512, -0.220], confident-wrong +0.171 [+0.073, +0.293], both a difference; minus `baseline`: accuracy -0.049 [-0.244, +0.146], confident-wrong +0.024 [-0.146, +0.195], no difference.
- Where it lost to `custom-metricflow` (15 cases right there, not here), each traced to what Lightdash dropped:
  - Metrics not translated, the agent improvising: `net_revenue_one_day`, `net_revenue_total` and `net_revenue_germany` (`net_revenue_eur` is cross-model derived: the agent subtracted returns itself, or gave revenue as net revenue), `view_to_cart_rate` (a conversion metric: it divided cart sessions by site sessions on one day, 60%); all confident-wrong.
  - The semi-additive loss above: `budget_left_end_of_september` asked September, Lightdash summed every September snapshot, and the agent answered €217,230 "the sum of each campaign's last September snapshot", repeating the description over the SQL that contradicts it; confident-wrong.
  - No entity-joined dimension: `revenue_germany`, `net_revenue_germany`, `candidates_in_interview_as_of` and `cost_per_lead_search`; the agent tried `candidate__stage` as a filter (refused by the tool), then gave the all-country or all-stage figure saying it could not split it.
    The rule scores three of these confident-wrong because "cannot split … so this figure covers all countries" is outside its hedge list; read by hand they are hedged (wrong, not confident-wrong), which the blind judge would decide.
  - Declined where MetricFlow's richer metrics answer: `revenue_signup_cohort`, `orders_over_100`, `signup_to_first_order_rate`, `repeat_revenue_share`, `page_views_one_day`, `monthly_active_customers`.
  - `revenue_fiscal_q3`: the fiscal quarter is a MetricFlow custom grain Lightdash has no counterpart for; the agent took calendar July to September and said so (wrong).

## What it means for the verdict

- Lightdash's free query API computes MetricFlow's numbers for what it translates: 35 of 36 metrics agree to the cent on the fixture, totals and every day; the one miss is a semi-additive metric turned into a plain sum without a warning, the worst kind of loss for an agent because the description still promises the right definition.
- As an agent's front door it is not worth adopting over our own MetricFlow tools: on the 41 cases it is 36.6 points less accurate and 17.1 points more often confidently wrong than `custom-metricflow` (both intervals exclude zero), and no better than text-to-SQL `baseline`.
  The losses are the translation's gaps, not the API's: untranslated derived, conversion and cumulative metrics, dropped entity joins (dimensions across models), custom grains and the non-additive dimension; an agent over Lightdash reconstructs those by hand, the confident-failure mode the bet looks for.
- This sharpens #334's "borrow, don't adopt": Lightdash's translation table is a map of what any compile-MetricFlow-elsewhere path loses, and now one of those losses (semi-additive metrics) is shown to be silent; a check like `363_lightdash_numbers.py` (every metric's total and by-day numbers against MetricFlow's) is what such a path needs before an agent trusts it.

## Still unknown

- Runs 2 and 3 of the 41 cases and all three runs of the other 55 (the free quota); the blind judge's verdicts on the two unclear turns and the three hedged answers.
- Whether giving the agent each metric's compiled SQL in the catalog (not only after a query) would make it notice the `remaining_budget_eur` contradiction.
- Whether Lightdash's `meta.joins` (hand-written joins between explores) recover the entity-joined dimensions; not tried (a team would have to write them per model, beside the semantic layer).
- The same check on `make dbt-build`'s `warehouse` data; not run, since the frozen set's expected numbers come from `dbt_dev`.

## Sources

- `measured`: the runs above; probes `334_lightdash.sh`, `334_lightdash_server.sh`, `363_lightdash_numbers.py`, `363_lightdash_agent.py`, `328_mcp_live.py`; [`eval-custom-lightdash.jsonl`](../eval-custom-lightdash.jsonl), [`eval.md`](../eval.md).
- References, not read this session (every fact above is `measured`; the async endpoint was found by trying it): Lightdash's API (<https://docs.lightdash.com/api-reference/v2/introduction>), MetricFlow's non-additive dimensions (<https://docs.getdbt.com/docs/build/measures#non-additive-dimensions>).
