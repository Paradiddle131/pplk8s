# Blind audit: frozen set (`semantic_bet.yaml`), cases 49 to 96

Auditor: blind subagent, 2026-11-06.
Scope: `questions:` entries 49 (`leads_mtd`) to 96 (`bet_sessions_per_order`), every turn.
Read: the set, RULE.md, `evaluation.py` (`carries`, `as_expected`, `DATES`, `NUMBER`, `ASKS_WHICH`), `bet_rule.py`, `bet_eval.py` (`score_turn`), `dbt/dev/fixture*.sql`, `dbt/target/catalog/agent.json`, and `tests/e2e/agent-fixture.sh` (how dbt_dev is built: one `dbt build`).
No result file, log, ledger, issue or PR was opened.
Every expected, naive and legacy SQL was run on `dbt_dev`; each answer was re-derived independently from `silver.*` (queries quoted in the table, `Q` = `docker exec pplk8s-warehouse-1 psql -U warehouse -d dbt_dev -At -c`).

Scorer facts used below (code, not results):
- A number turn is right when any stated number is within 0.006 of an expected number or equals it rounded to the decimals stated (`carries`); numbers the question holds are not excluded from that match (`stated()` only feeds the decline and hedge tests); `HH:MM` times are not stripped, so `10:00` states 10 and 0.
- A `define` turn is right only when the answer contains the catalog description verbatim after case and punctuation folding (`score_turn`: `_words(described[name]) in _words(text)`).
- An `ambiguous` turn is right when it carries every meaning's number or when any sentence ends in `?` and contains `which`, `or`, `mean` or `meant` (`ASKS_WHICH`); a probe confirms "Revenue was 981.69 EUR. Would you like it broken down by country or by day?" passes.

| case | verdict | category | evidence | proposed fix |
|---|---|---|---|---|
| 49 `leads_mtd` | ok | | Expected 42; `select count(*) from silver.leads where created_date between '2026-09-01' and '2026-09-10'` = 42 (distinct `lead_id` 42). One reading; covered by `leads_mtd`. | none |
| 50 `followup_by_country` | ok | | T1 1850.34 (`gold.daily_sales` 10-01..02). T2 410.75: DE customers 4 and 10, non-cancelled: 15.75+300+64 (10-01) + 31 (10-02) = 410.75. Covered by `revenue_eur` by `customer__country`. | none |
| 51 `followup_day_before` | ok | | T1 868.65 (10-02), T2 981.69 (10-01); both re-derived from `silver.orders` non-cancelled. | none |
| 52 `followup_switch_metric` | ok | | T1 15 = ORD-0001..0015, cancelled included, as asked. T2 964.19 = 981.69 − returns dated 10-01 (12.50+5.00), the governed net revenue (`exposed.net_sales_daily`). Returns-by-order-date reading would give 956.94, but the governed definition and the trusted table agree on 964.19. 15 is small, but the likely wrong answers (13 non-cancelled) do not carry it. | none |
| 53 `followup_how_computed` | defect | scorer | T1 964.19 right. T2 `define: net_revenue_eur` passes only if the answer contains "revenue minus partner returns finance s net sales" verbatim (catalog text "Revenue minus partner returns (finance's net sales)."). A correct explanation ("non-cancelled order revenue less the partner return amounts dated that day") is scored wrong; an arm that never sees the catalog descriptions cannot pass it whatever it understands. | retire, or a later version with a judged or keyword-set define turn |
| 54 `followup_rate_how_computed` | defect | scorer | T1 0.1667: 5 cancelled of 30 on 10-01..02 (2/15, 3/15; the mean of daily ratios is equal here). T2 `define: cancellation_rate` needs "share of orders cancelled" contiguous; "cancelled orders divided by all orders" or "the share of orders that were cancelled" fails. Same flaw as 53. | retire, or a later version as 53 |
| 55 `ambiguous_sales` | defect | scorer | T1 numbers right (981.69 gross, 964.19 net). But `ASKS_WHICH` passes any answer with a closing "...by day or by country?" offer, so a silent gross pick with a generic follow-up offer scores right on the turn meant to test asking. T2 964.19 right. | retire, or a later version whose ambiguous check needs both numbers or a question naming gross/net |
| 56 `ambiguous_customers` | defect | scorer, fixture | Expected 9 / 10 / 30: signups in Sept = customers 22..30 (9); distinct buyers = 10; to date = 30. Same `ASKS_WHICH` leniency as 55. In addition, 10 is fixed by construction (every weeks-fixture order goes to customers 1-10, so "distinct buyers" in any multi-day window is all base customers), and all three are small counts. | retire, or as 55 |
| 57 `planted_campaign_top_spend` | ok | | 130.00 = campaign 1 on 10-01 after the rerun correction (silver keeps 130, not 120). Not 0, so the planted "0 EUR" cannot match. Covered (`ad_spend_eur` by `campaign` entity). | none |
| 58 `planted_campaign_least_spend` | ok | | 20.00 = campaign 7, 10+10 over 10-01..02 (search 230, social 140). 20 is a small number, but the plausible wrong answers (10 per day, 140 social) do not carry it. | none |
| 59 `planted_top_customer` | ok | | 2356.00 = customer 10, non-cancelled lifetime (`silver.orders` group by customer: 10 → 2356.00, 2 → 2331.00). Including cancelled gives 2510.75 (not what "spent" means); net of returns 2328.75 (customer 10 has R-3), a weaker reading. Covered: `revenue_eur` lists the `customer` entity. | none (note: net-of-returns reading is possible but not the governed one) |
| 60 `bet_cancellation_rate_period` | ok | | 0.0952 = 20/210 cancelled, `silver.orders` 08-17..10-02. Naive (mean of daily ratios) 0.0709 differs, trap holds. | none |
| 61 `bet_customers_september` | defect | fixture, scorer | 10 = `count(distinct customer_id)` with or without cancelled (both 10): the weeks fixture assigns every order to customers 1-10, so the answer is "all base customers" by construction, and the trap's cancelled filter cannot matter. 10 is a common count (also the number of pre-2026 customers). Naive 110 differs. | retire |
| 62 `bet_top_country_september` | ok | | `silver.orders` ⋈ `silver.customers`, non-cancelled Sept: DE 2665.50, GB 2634.00, TR 2412.00... DE unique. Legacy 2857.00 differs, distractor holds. | none |
| 63 `bet_weekday_most_orders` | defect | fixture | 6 whole weeks, 3+i%3 orders a day: every weekday has exactly 24 orders (22 non-cancelled). `select to_char(order_date,'Dy'), count(*) ... 08-17..09-27 group by 1` → all seven = 24. The "which day" has no answer and 24 is constant. | retire |
| 64 `bet_ad_spend_september` | ok | | `sum(spend)` Sept = 6270.00. | none |
| 65 `bet_channel_lowest_cpl` | ok | | Spend/leads by channel 08-17..10-02 from silver: email 470/14 = 33.571, search 5795/134 = 43.25, social 3290/63 = 52.22. Naive 10 differs. | none |
| 66 `bet_lead_to_booking_september` | ok | | Distinct booked Sept leads / Sept leads = 0.3857; every booking is 5 h after its lead, so the 30-day window does not matter. | none |
| 67 `bet_top_call_topic` | ok | | `silver.call_signals` 08-25..10-02: product 24, returns 16, delivery 6, pricing 6. Golden labels exist only for the 12 October calls, so model labels are the only full source. | none |
| 68 `bet_topic_objection_rate` | ok | | Sept: returns 8/11 = 0.7273, product 8/16 = 0.5, pricing 0/4, delivery 0/1. | none |
| 69 `bet_top_campaign_spend` | ok | | Search campaign 1: 5795.00 (social 3290, email 470). Covered via `campaign` entity. | none |
| 70 `bet_top_return_reason_share` | ok | | Returns dated 10-01..04: damaged 12.50 of 24.75 = 0.505. One query by reason needs a division: uncovered. | none |
| 71 `bet_avg_days_to_return` | ok | | Date differences 0, 0, 1 → 0.333. Note: in the fixture R-1's return timestamp (10-01 10:00) precedes its order (ORD-0014, 21:00), a fixture inconsistency that only matters to a timestamp reading (mean 0.107 days), which the question's "order date ... return date" rules out. | none |
| 72 `bet_median_session_minutes` | defect | readings | Ten sessions, five with one event (0 min): durations 0,0,0,0,0,3,5,6,10,15 → median 1.5. Excluding single-event sessions (the usual "duration is undefined for a one-hit session" convention): 3,5,6,10,15 → median 6 (`... having count(*)>1` = 6). The case accepts only 1.5. | retire, or a later version that states how single-event sessions count |
| 73 `bet_peak_page_view_hour` | defect | fixture, scorer | Page views by UTC hour: 9 → 2, 10 → 2, the rest 1: a two-way tie, and the expected 2 is a tiny number any answer may state. | retire |
| 74 `bet_median_reply_hours` | ok | | Replied messages sent 10-01..03: 6, 19, 2, 7 h → median 6.5. | none |
| 75 `bet_applicants_reaching_interview` | defect | expected_sql, fixture | dbt_dev is built by one `dbt build`, so `silver.candidate_stage_snapshots` holds one row per candidate (6 rows, current stage only) and `silver.candidate_stages` likewise; the stage history the fixture describes is not in the warehouse. Sept applicants: K-001, K-002, K-005. The fixture's source rows show K-002 in interview on 10-02 before rejection, and K-005 in offer (beyond interview), so the business answer is 3/3 = 100%; the expected 2/3 = 0.667 counts K-002 out only because the history is missing. No trusted table lets an agent see K-002's interview. | retire |
| 76 `bet_median_days_to_hire` | defect | fixture, readings | Only two hires (K-005 7.2083, K-001 4.9583), so the median equals the mean = the governed `time_to_hire_days` (6.0833): an "uncovered" median that the covered average answers by construction. Whole-day reading (dates 09-25→10-02 = 7, 09-28→10-03 = 5) gives 6, which `carries` rejects (|6−6.0833| > 0.006, no decimals). | retire |
| 77 `bet_istanbul_warmer` | defect | fixture | Both cities use the same sine formula, base 19 vs 11: avg, min and max differ by exactly 8.00 every day (`gold.daily_weather`: 19/14/24 vs 11/6/16). Any reading gives 8, a small constant. Reach also applies (weather tables). | retire |
| 78 `bet_ad_spend_per_order` | ok | | 6270 / 110 non-cancelled Sept orders = 57.00 (120 orders incl. cancelled, which the question excludes). | none |
| 79 `bet_delivery_calls_per_100_shipped` | defect | scorer, fixture | One delivery call in Sept (09-09) over 50 shipped orders → 2.0. The expected 2 is a tiny number (e.g. any "2 October"-free mention of 2 calls/weeks carries it), and the figure rests on one model-labelled call. | retire |
| 80 `bet_median_order_september` | ok | | 110 non-cancelled orders: `percentile_cont(0.5)` 117.375 (mean of the two middle values, the standard median); `percentile_disc` 116.75 is the less usual reading. | none |
| 81 `bet_p90_order` | doubt | readings | `percentile_cont(0.9)` 158.125; `percentile_disc(0.9)` / nearest rank 158.00, outside tolerance, and "158 EUR" fails the rounding match. Both are textbook p90 definitions. Settled by the owner deciding whether interpolated percentile is the set's definition (it is Postgres' and BigQuery's `PERCENTILE_CONT`). | accept both in a later version, or retire |
| 82 `bet_customers_over_three_orders` | defect | fixture, scorer | 10 = all customers who ever ordered in the window (also 10 non-cancelled): every customer 1-10 places ~21 orders by construction; 10 is a common count. | retire |
| 83 `bet_median_signup_to_first_order` | ok | | First orders in October: customers 12..30 step 3, 13..61 days → median 37. | none |
| 84 `bet_aov_old_vs_new_customers` | ok | | Pre-2026 signups 102.666, 2026 signups 41.00 (7 orders) → 61.666. | none |
| 85 `bet_median_days_to_return` | defect | scorer | Expected 0 (0, 0, 1). Any answer stating a clock time ("10:00") or any 0 carries it: probe "median 0.15 days ... logged at 10:00 and 15:30" scores right. Timestamp reading gives 0.146. | retire |
| 86 `bet_damaged_vs_wrong_size` | ok | | 12.50 − 5.00 = 7.50 (one return each). | none |
| 87 `bet_median_days_lead_to_booking` | defect | fixture, scorer | All 54 Sept bookings are 5 h after their lead, so every gap is 0 days by construction; expected 0 carried by any stated 0 or `HH:00`. Timestamp reading 0.208 days. | retire |
| 88 `bet_weekday_avg_spend` | ok | | Daily totals by weekday, Sept: Thu 215.00 (4 days), Wed 212, Tue 208 ...; unique. | none |
| 89 `bet_cart_to_checkout_minutes` | doubt | scorer | Two sessions (S-0002 6 min, S-0008 4 min) → 5. 5 is small, and the window holds exactly 5 add-to-cart events, so a wrong answer reporting that count carries it (probe confirmed). Settled by judging how often answers state the event count. | none, or a later version with more sessions |
| 90 `bet_most_email_opens` | defect | fixture, scorer, label | Three customers (1, 4, 9) opened 1 email each: a three-way tie, expected 1. Also covered, not uncovered: `customer_actions` filtered on `customer_action__action_type = email_open`, grouped by the `customer` entity, ordered, limit 1. | retire (relabel to covered if kept) |
| 91 `bet_peak_checkout_hour` | defect | scorer | Checkouts at 09:10 and 09:06 → hour 9, 2. The expected 2 is tiny (probe: "3 including a duplicate, out of 2 sessions" passes). | retire |
| 92 `bet_p75_reply_hours` | defect | readings, scorer | Replies 2, 6, 7, 19 h: `percentile_cont` 10, nearest rank / `percentile_disc` 7, Excel `PERCENTILE.EXC` 16. With four values the definitions spread widely, and 10 is a common number. | retire |
| 93 `bet_median_days_to_interview` | defect | fixture, scorer, expected_sql | Expected 2 comes from K-003 alone (the only `current_stage = 'interview'` row, no stage history; see 75). The business answer (K-001, K-002, K-003 each 2 days) is also 2: constant, tiny. Timestamp reading 2.21. | retire |
| 94 `bet_wetter_day_nl_orders` | defect | fixture, scorer | Amsterdam precipitation is 2.40 mm on both days (same formula), so "which day was wetter" has no answer; NL orders are 3 on each day, so the expected 3 is fixed and small. | retire |
| 95 `bet_revenue_per_ad_euro` | ok | | 12582.75 / 6270 = 2.0068. | none |
| 96 `bet_sessions_per_order` | ok | | 7 sessions / 75 orders (all placed, as "per order placed" reads; 66 non-cancelled would give 0.106). Note: session data covers only 09-20 and 10-01..03 while orders cover every day, so the ratio reflects the sparse fixture, but it is computable as asked. | none |

## Defects and doubts, most severe first

1. **75 `bet_applicants_reaching_interview`**: the expected number is wrong for the business question (0.667 vs 1.0), because dbt_dev keeps no candidate stage history (one `dbt build`, one snapshot row per candidate).
2. **63 `bet_weekday_most_orders`**: seven-way tie at 24 by construction; the "which day" has no answer.
3. **94 `bet_wetter_day_nl_orders`**: precipitation tie (2.40 mm both days) and NL orders 3 on both days.
4. **90 `bet_most_email_opens`**: three-way tie at 1, and mislabelled (one metric query answers it: covered).
5. **73 `bet_peak_page_view_hour`**: tie between 09:00 and 10:00 at 2.
6. **77 `bet_istanbul_warmer`**: difference fixed at 8 by the weather formula.
7. **61 `bet_customers_september`** and **82 `bet_customers_over_three_orders`**: 10 = every base customer by construction; common count.
8. **85 `bet_median_days_to_return`** and **87 `bet_median_days_lead_to_booking`**: expected 0, carried by any stated `HH:00` time.
9. **91 `bet_peak_checkout_hour`**, **79 `bet_delivery_calls_per_100_shipped`**, **93 `bet_median_days_to_interview`**: expected 2, tiny; 93 also rests on the missing stage history.
10. **76 `bet_median_days_to_hire`**: median of two equals the governed average; whole-day answer 6 rejected.
11. **92 `bet_p75_reply_hours`**: percentile definitions give 10 / 7 / 16; 10 is common.
12. **72 `bet_median_session_minutes`**: 1.5 vs 6 depending on single-event sessions.
13. **53 `followup_how_computed`**, **54 `followup_rate_how_computed`**: `define` turns need the catalog sentence verbatim; a correct paraphrase fails, and arms without the catalog cannot pass.
14. **55 `ambiguous_sales`**, **56 `ambiguous_customers`**: `ASKS_WHICH` passes a silent pick that ends with any "... or ...?" offer (56 also has a by-construction 10).
15. Doubt **81 `bet_p90_order`**: interpolated 158.125 vs nearest-rank 158.00.
16. Doubt **89 `bet_cart_to_checkout_minutes`**: expected 5 equals the window's add-to-cart count.

Cross-cutting note, not counted per case: "which X, and how much" cases score only the number, so an answer that lists every group's total passes even if it names the wrong winner (57, 58, 62, 65, 67, 68, 69, 88). The risk is low where totals are distinct, so these stay ok.

## Counts

ok 26, defect 20, doubt 2 (48 cases).
