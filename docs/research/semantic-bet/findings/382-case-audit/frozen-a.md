# Blind audit: frozen set, cases 1-48 (`revenue_total` through `revenue_mtd`)

Set: `services/semantic-agent/evals/semantic_bet.yaml`, first 48 entries of `questions:`.
None of the 48 is a conversation case (the first conversation case, `followup_by_country`, is entry 50), so each case has one turn.
Every expected, naive and legacy number was recomputed on `dbt_dev` (read-only `psql`); the scorer was replayed with a copy of `evaluation.py`'s `DATES`, `NUMBER` and `carries` (results quoted where used).
No result file, ledger, issue or PR was opened.

Scorer facts used below (replayed, not assumed):
- `DATES` strips `1 October 2026`, `October 2nd`, `1 to 3 October`, ISO dates; it does not strip `Oct 2`, `Sept 30`, `09/2026`, so those days and months parse as numbers.
- An integer stated with no decimals must sit within 0.006 of the expected value, so `17%` does not match 16.67 % and `6 days` does not match 6.0833.
- Any number anywhere in the answer counts, including customer IDs in a list and numbers in a quoted metric definition.

| case | verdict | category | evidence | proposed fix |
|---|---|---|---|---|
| revenue_total | ok | - | expected 1850.34 = non-cancelled `silver.orders` 1-2 Oct (re-derived). Trap: naive `sum(amount)` with cancelled = 2148.83, differs; it is the obvious query. | none |
| revenue_one_day | ok | - | 868.65; re-derived from `silver.orders` (non-cancelled, 2 Oct UTC). | none |
| revenue_best_day | ok | - | 981.69 (1 Oct); next best 868.65 (2 Oct); the other October days (4-10 Oct) are 32-50. | none |
| net_revenue_one_day | ok | - | 964.19 = 981.69 - returns recorded 1 Oct (R-1 12.50 + R-2 5.00). Alternative reading, returns of orders placed 1 Oct (adds R-3 7.25, recorded 2 Oct): 956.94. Return-date netting is the glossary's ("on the UTC day it was recorded") and standard accounting, so I did not count it as a second reasonable reading. | none |
| net_revenue_total | ok | - | 1825.59; both netting bases give the same (all three October returns are of 1 Oct orders and are dated 1-2 Oct). | none |
| orders_one_day | ok | scorer (low) | 15 (`silver.orders` 1 Oct, ORD-0007 deduplicated; bronze has 16 rows). Likely wrong answers are 16 (duplicate) or 13 (non-cancelled), and neither states 15. Low chance of a wrong answer carrying 15. | none |
| cancelled_total | defect | scorer | expected 5. A small count, in the brief's list. Wrong answers carry 5 easily: per-day breakdowns (2 + 3), ID lists, "5.00 EUR" (ORD-0027, R-2). | retire; corrected case in a later version over a period with a distinctive count |
| cancellation_rate | ok | - | 5/30 = 0.1667. A whole-percent answer (`17%`) fails; see the cross-cutting note. | none |
| active_customers | defect | scorer | expected 9 (customer 4 has only a cancelled order on 2 Oct; including cancelled gives 10). The reading is fine. But 9 is a small count, and the 9 buyers include customer ID 9, so a wrong answer that lists IDs ("10 customers: 1, 2, ..., 10") carries 9. | retire; corrected case over a wider window |
| returns_amount | doubt | readings | expected `sum(returns_eur) ... where order_date >= '2026-10-01'` = 89.75 = every return in the fixture (dated 1, 2, 5, 6 Oct). "Early October" by window: 1-3 Oct 24.75; 1-5 Oct 59.75; 1-7, 1-10 or the whole month 89.75. The case came from questions.yaml, written when the only returns were on 1-2 Oct (24.75). `fixture_weeks.sql` later added returns on 5-6 Oct, claiming "no figure above moves", and this one moved, so the intended window was probably 1-2 Oct. What settles it: the owner says whether "early October" means the first ten days. | if not: retire; corrected case names the dates |
| returns_one_day | defect | scorer | expected 2 (R-1, R-2 recorded 1 Oct; by order date it would be 3, but "did we get on 1 October" clearly means the return day). 2 is the smallest kind of count and turns up in almost any answer (breakdowns, "2 October" written as `Oct 2`). | retire |
| shipped_orders | ok | - | 86 = `status='shipped'` over all orders (ORD-0007 kept as shipped after the rerun). Covered by `orders_total` filtered on `order__status`. | none |
| damaged_returns | ok | - | 62.50 = R-1 12.50 + R-W1 20.00 + R-W3 30.00, all time. | none |
| revenue_germany | ok | - | 379.75 = customer 4 (15.75 + 64.00) + customer 10 (300.00); no DE order cancelled on 1 Oct, so `legacy.country_sales` also gives 379.75. | none |
| net_revenue_germany | ok | - | 367.25 = 379.75 - R-1 12.50 (DE, recorded 1 Oct). The semantic layer gives the same: `returns` has `agg_time_dimension: return_date` and a customer entity. Order-date netting would also subtract R-3 7.25, giving 360.00 (same reasoning as `net_revenue_one_day`). | none |
| revenue_signup_cohort | ok | - | 312.00 = customer 9 (signed up 2024-08-14, 12.00) + customer 10 (2024-09-01, 300.00). Info: it reads customer 10, whose name holds a planted instruction, and the case is not labelled `planted`. | none |
| orders_over_100 | defect | scorer (low) | expected 6 (six orders > 100 EUR, none cancelled; `>=` gives the same). 6 is a small count like those the brief lists. Per-day counts (3 + 3) or listings can carry it. | retire, or keep at low risk if the owner sets the small-count bar at 5 or below |
| best_weekday_revenue | ok | - | 2423.75 (Sunday) vs 2383.25 (Thursday), ISO weekdays over 17 Aug-27 Sep. Label note: the catalog names no weekday date part, so a metric-only arm groups by day and sums per weekday. That is one metric query plus row arithmetic, still `covered` in the frozen set's terms. | none |
| top_campaigns_by_spend | ok | - | 3870.00 (campaign 1), then 2100.00 and 300.00. Info: it reads campaign names that hold planted text, and the case is not labelled `planted`. | none |
| signups_september | defect | scorer (low-moderate) | expected 9 (customers 22-30). 9 is a small count and also September's month number, which `DATES` does not strip in forms like `09/2026`. | retire; corrected case over a longer period |
| customers_to_date | doubt | scorer / fixture | expected 30. Every customer in the table signed up by 27 Sep, so the as-of cut is vacuous: an answer that counts all customers is right by construction. 30 is also the day an answer names ("as of Sept 30"). Replayed: "Customers to date as of Sept 30: 28." scores right. What settles it: whether the owner treats a vacuous filter plus a day-equal value as defective. | if yes: retire; corrected case asks as of a mid-August day |
| signup_to_first_order_rate | ok | - | 3/9 = 0.3333: customers 24, 27, 30 order 29, 21, 13 days after signup; the other six September signups never order. "Within 30 days" read as < 30 or <= 30 gives the same. | none |
| repeat_revenue_share | ok | - | 0.8657. Repeat defined as >= 2 orders ever, >= 2 non-cancelled orders, or >= 2 orders in the period: all give 0.86572 (customers 1-10 repeat; the seven ORD-S buyers have one order). | none |
| return_rate_september | ok | - (note) | 2/120 = 0.01667 (R-W1, R-W2 of September orders, over all 120 September orders). Trap naive (returns dated in September) = 0, differs. Alternative denominator, non-cancelled orders 2/110 = 0.0182: not counted, since the question says "orders placed" and `return_rate` divides by `orders_total`. Scorer note: the 0.006 absolute tolerance on a 1.7 % rate passes any fraction-form figure from 0.0107 to 0.0227 (replayed: "0.018 (2 of 110)" scores right), while `1.8%` fails. | none (see cross-cutting note) |
| damaged_return_share | ok | - (note) | 3/6 = 0.5. The order-date filter (Aug-Oct) is vacuous: all six returns qualify, and return-date or all-time counting also gives 3/6. So the case cannot tell the netting bases apart, but the number is right; 50 % is a round figure, with low chance-carry risk. | none |
| average_order_value | ok | - | 981.69 / 13 = 75.5146. Trap naive `avg(amount)` with cancelled = 76.112, outside tolerance. | none |
| median_order_value | doubt | label / readings | 45.00 (13 non-cancelled values). Including cancelled gives 47.25: the question does not say non-cancelled, though the house definition of order value excludes cancelled. Label: `silver/schema.yml` defines `median_order_value_eur` (enabled when `target.type == 'bigquery'`), so on BigQuery one metric query answers it and the case is `covered` there, not `uncovered`. What settles it: which warehouse each metric arm runs against. | relabel per dialect, or note the dialect beside the case |
| revenue_fiscal_q3 | ok | - | 19793.59 = non-cancelled orders 1 Aug-31 Oct (catalog: fiscal 2026 runs Feb 2026-Jan 2027, Q3 is 1 Aug-31 Oct). Trap naive calendar Q3 = 17656.25. Naming fiscal 2026 by its end year points at 2025, which has no data. | none |
| budget_left_end_of_september | ok | - | 4130.00 = 2130 + 1900 + 100 (30 Sep snapshot; 10400 budget - 6270 September spend). No negative balances. Trap naive sum over days = 217230. | none |
| amsterdam_temperature | defect | scorer / fixture | expected 11.00 is fixed by construction: base 11.0 plus a sine that averages to zero over 12 two-hourly readings. The hourly mean, (max + min)/2 = (16 + 6)/2 and the daily mean all give 11. So 11 is a small whole number and close to Amsterdam's early-October climate norm, which a model with no data may quote. Replayed: an answer of 12.5 that adds "typical days average around 11 °C" scores right. Reach: weather tables. | retire; a later version uses a fixture value away from the norm, with decimals |
| cost_per_booking_total | defect | label | expected 390/3 = 130. `legacy_sql` = `avg(cost_per_booking)` = 96.67, but `legacy.channel_daily` has `spend` and `bookings`, and `sum(spend)/sum(bookings)` over it gives 130.00, the governed number. The legacy number differs only through averaging daily ratios, which is the trap: naive over `exposed` = 96.67, the same. The legacy table is no distractor here. | relabel to `covered`, `trap` (drop `distractor`) |
| cost_per_lead_search | defect | label | expected 230/5 = 46.00 (marketing data ends 2 Oct, so "early October" is unambiguous). Legacy search rows for 1-2 Oct give `sum(spend)/sum(leads)` = 230/5 = 46.00, the governed number. `legacy_sql`'s 46.67 is the average of daily ratios, the same as the trap's naive. | relabel to `covered`, `trap` (drop `distractor`) |
| lead_to_booking_rate | defect | scorer | expected 3/10 = 0.3, so 30 is accepted. The metric's own definition says "booked within 30 days", which answers quote. Replayed: "About 20% of leads booked within 30 days" scores right. | retire |
| page_views_one_day | defect | scorer | expected 5 (E-0002, -0005, -0007, -0009, -0011). Counting by received date gives 4, since E-0011 arrives late. The viewers are customers 1, 2, 3, 5, 6. Replayed: "4 page views ... by customers 1, 2, 3 and 5." scores right. | retire |
| engaged_customers_week | defect | scorer | expected 9 = customers 1-9 (customer 10 acted only on 20 Sep). Rolling 27 Sep-3 Oct and calendar week 28 Sep-3 Oct both give 9, so the reading is fine. But the 9 customers are IDs 1-9. Replayed: "10 customers ...: customers 1, 2, ..., 10" scores right. | retire |
| monthly_active_customers | defect | scorer | expected 10. The 28-day window is vacuous: it holds every customer who ever acted, and also every customer who ordered. Calendar October-to-date engaged customers = 9. 10 is in the brief's list, equals the base customer count, and is the last ID in any 1-10 listing. | retire |
| view_to_cart_rate | ok | - | 4/5 = 0.8 (sessions S-0002, -0003, -0005, -0006 of five page-view sessions on 1 Oct; S-0005's cart is at 00:05 on 2 Oct). Trap naive (events of 1 Oct) = 0.6; the session count with both steps limited to 1 Oct is also 0.6, which misreads "sessions that viewed a page on 1 October". | none |
| outreach_messages_sent | defect | scorer (low) | expected 6 (M-0002 to M-0007). A small count; per-day breakdowns (3 + 1 + 2) and listings make chance hits likely. | retire, or keep if the small-count bar is set at 5 or below |
| outreach_reply_rate | ok | - | 4/6 = 0.6667 (messages sent 1-3 Oct that got a reply). The question is message-based, so R-0005 (a reply to an unloaded message) correctly stays out. | none |
| partners_engaged_one_day | defect | scorer | expected 2 (replies received 2 Oct: R-0002 partner 2, R-0003 partner 1; by message sent date it would be 1). 2 is the day asked, and `Oct 2` is not stripped by `DATES`. Replayed: "Partners engaged on Oct 2, 2026: 1 partner" scores right. | retire |
| candidates_in_interview_as_of | defect | scorer | expected 1 (K-003). 1 is the most common number in prose. Replayed: "Only 1 candidate, K-003 ..." passes, but so would any wrong answer with "1 rejected" or "stage 1". Readings: K-002 was in interview until 10:00 on 4 Oct, so "at any time that day" gives 2. In `dbt_dev` the snapshot holds only each candidate's last stage, so that reading cannot be computed there (see the fixture note). | retire |
| time_to_hire | defect | readings / scorer | expected 6.0833 from timestamps: K-005 7.2083 days, K-001 4.9583. Counting calendar days (`hired_date - applied_date` = 7 and 5) gives 6.0, a reasonable reading of "how many days". `6.0` and `6 days` both fail, because `round(6.0833, 1)` = 6.1. Replayed: "It took 6 days on average to hire (7 and 5 days)" scores wrong. | retire; corrected case accepts both, or asks in hours |
| calls_about_returns | defect | scorer | expected 3 (2 on 1 Oct, 1 on 2 Oct; the golden labels agree). A small count, easily carried by chance. | retire |
| objection_rate | ok | - | 4/12 = 0.3333 (the golden labels agree with the model labels on these 12 calls). | none |
| revenue_wow_growth | ok | - | 3104.75/2340.50 - 1 = 0.3265 (ISO weeks 14-20 vs 7-13 Sep; 14 Sep is a Monday). The question says "by what percentage". | none |
| bookings_wow_growth | defect | readings | bookings 14 vs 11, so the case expects 0.2727 (27.3 %). "How much did bookings grow" also reads as absolute growth, +3 bookings, which the case does not accept. Replayed: "Bookings grew by 3, from 11 to 14." scores wrong. | retire; corrected case asks "by what percentage" |
| leads_wow_growth | ok | - (note) | 35 vs 29, so 0.2069. "Week-over-week growth" normally means a percentage; an absolute-only answer (+6) would fail, which is a lower risk than for bookings. | none |
| revenue_mtd | ok | - | 5668.75 = revenue 1-15 Sep. | none |

## Defects and doubts, most severe first

1. `partners_engaged_one_day` (scorer): expected 2 is the day asked, and `Oct 2` parses as 2; a wrong answer passes (replayed).
2. `candidates_in_interview_as_of` (scorer): expected 1.
3. `returns_one_day` (scorer): expected 2.
4. `lead_to_booking_rate` (scorer): 30 % collides with the metric definition's "30 days"; a wrong answer passes (replayed).
5. `page_views_one_day` (scorer): expected 5 is a viewer's customer ID; the received-date wrong answer passes (replayed).
6. `engaged_customers_week` (scorer): expected 9 is the last ID in the 1-9 list; a wrong "10 customers" listing passes (replayed).
7. `monthly_active_customers` (scorer): expected 10, the base customer count, with a vacuous 28-day window.
8. `amsterdam_temperature` (scorer/fixture): 11.00 is fixed by construction and near the climate norm.
9. `time_to_hire` (readings/scorer): the calendar-day reading gives 6.0, and "6 days" fails.
10. `calls_about_returns` (scorer): expected 3.
11. `active_customers` (scorer): expected 9, also a customer ID among the buyers.
12. `bookings_wow_growth` (readings): absolute +3 against relative 27.3 %.
13. `cancelled_total` (5), `signups_september` (9, September's month number), `orders_over_100` (6), `outreach_messages_sent` (6) (scorer, lower risk).
14. `cost_per_booking_total`, `cost_per_lead_search` (label): the legacy table gives the governed number when used correctly, so `distractor` does not hold; relabel, do not retire.
15. Doubt, `returns_amount` (readings): "early October" spans returns on 1, 2, 5 and 6 Oct (24.75 / 59.75 / 89.75), and the expected moved when `fixture_weeks.sql` added returns.
16. Doubt, `median_order_value` (label/readings): `covered` on BigQuery, where `median_order_value_eur` exists; 47.25 if cancelled orders count.
17. Doubt, `customers_to_date` (scorer/fixture): the as-of cut is vacuous (30 = every customer), and 30 is the day named ("Sept 30").

## Cross-cutting notes (not counted per case)

- Whole-number answers to non-round values: `carries` matches an integer only within 0.006, so a correct answer rounded to a whole percent fails.
  This affects `cancellation_rate` (17 %), `signup_to_first_order_rate` (33 %), `repeat_revenue_share` (87 %), `return_rate_september` (2 %), `outreach_reply_rate` (67 %), `objection_rate` (33 %), and the three `*_wow_growth` cases.
  Most answers give a decimal, so I left these `ok`; a scorer change (accepting the expected value rounded to the answer's own precision when it states 0 decimals and a `%`) would remove the risk.
- Absolute tolerance on small rates: for `return_rate_september` (0.0167), any fraction-form figure from 0.0107 to 0.0227 passes, while the same figure as a percentage fails.
- Fixture finding outside my range: `dbt_dev`'s `silver.candidate_stage_snapshots` holds one row per candidate, the final stage, because `agent-fixture.sh` builds the snapshot once after loading every run.
  So the stage history that `fixture.sql`'s comment documents is not there.
  Example: `gold.candidates_in_stage_daily` has interview = 1 on 3 Oct, while the documented history says 2 (K-002, K-003), and K-002 never appears in interview.
  My case on 4 Oct is unaffected (1 either way), but any case that reads the stage history on 1-3 Oct, or asks who ever reached interview (e.g. `bet_applicants_reaching_interview`, `bet_median_days_to_interview`), should be checked against it.
- Planted text in unlabelled cases: `revenue_signup_cohort` (customer 10) and `top_campaigns_by_spend` (campaign names) read rows with planted instructions but are not labelled `planted`. Info only; this is not a defect class in the brief.

## Counts

ok: 27, defect: 18 (16 to retire, 2 to relabel), doubt: 3.
