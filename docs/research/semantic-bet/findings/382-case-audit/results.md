# Results audit of every logged run (pplk8s, issue #382)

Auditor: subagent, written 2026-11-06T14:14Z, after the four blind case audits (`frozen-a.md`, `frozen-b.md`, `hard-v1.md`, `hard-v2-new.md`).
No repo file was edited; scratch scripts and intermediate data are under `/tmp/claude-0/hv2/audit/scripts/`.

## Scope and method

- Logs read: every `docs/research/semantic-bet/eval-*.jsonl` (40 files), through `bet_eval.judged_logs(bet_eval.load_set(name))` for `frozen`, `hard` and `hard-v2`, so each turn carries the outcome the report computes now (recode on read plus the current judge model's verdicts from `judge.jsonl`).
- Runs: frozen 7,553 rows (8,024 turns), hard v1 3,222 rows (3,520 turns), hard-v2 3,403 rows, of which 3,222 are `carried_from: hard` copies (byte-identical text, outcome and `at` to their v1 rows, checked) and 181 are new-case rows (183 turns).
  Carried rows are counted once, under v1; a redaction key of a v1 run also matches its hard-v2 copy, because the overlay keys on `(arm, model, case, run, at)` and the copy keeps `at`.
- Expected numbers: `evaluation.expected_numbers` on `dbt_dev` (`postgresql://warehouse:warehouse@localhost:5433/dbt_dev`), per turn and per meaning, in every form `as_expected` gives.
- Consistency check: for every number turn, `bet_rule.number_right(text, expected)` today agrees with the logged "right" except 32 frozen turns that are right only by the blind judge (answers in words, e.g. "Two partners replied"); I treated those as judge-rights and read them.
- Every arm and model got the same mechanical checks; the flags were then read by me, turn by turn, and classified by hand (the classifications are data in `scripts/labels.py` and `scripts/labels.json`).

Classification rules I applied to right turns (check 2):
- genuine: the answer's own answer to the question is the matched number.
- chance: the matched number is incidental (a date or time, an ID, a count of something else, a number inside a quoted definition, a per-day value in a list, a table row count), or the answer declines or rejects that number, or the answer's main figure differs and the expected one appears only as a rejected alternative, or the answer refuses the asked figure and gives another figure that equals it only because of how the fixture was built.
  Every chance carry is misleading because of the test (the scorer's "any number counts" rule, its date stripping, or a fixture constant), so each is a redaction candidate.
- unclear: the answer offers two readings and labels both, the expected one second ("€1,007.15 (€868.65 excluding cancelled orders)"), or answers by channel where the fixture has one campaign per channel.
  Not redacted: the answer does give the expected figure as a labelled reading.

Mechanical flags (all arms alike), then read:
- check 2: no parsed match (judge-right in words); the first own number or the first bolded number is not an expected one; a competing number of the same magnitude before the match; the match sits after an ID-like word or inside a list of three or more integers; the match equals a number in the question; the answer contains decline or proxy wording; the match survives only through a date or time the scorer does not strip (`Sept 30`, `1–30 Sep`, `2026‑10‑03` with non-breaking hyphens, `T00:00Z`, `10:00`).
  That flagged 1,638 of the 8,670 right number turns (all 8,670 were also scanned for date-only matches); I read every flagged one.
  The other 7,032 right turns state an expected number as their first own figure, with no decline wording and no competing figure; I trusted those after spot checks of each small-number case.
- check 3: any not-right number turn whose text holds an integer within 5% that rounds to the expected value (`17%`, `158 EUR`), a truncation, an expected value written as a word (`Nine`, `half`, `a third`), a locale format, a unicode minus or a negative, an ×100 form of a value above 1, an "N of M" fraction equal to the expected rate, or an "Xh Ym" duration: 151 of 2,369 flagged and read.
- check 1: every answer scanned for error, exception, failure, refused, quota, rate limit, 429/403/500, timeout, permission, denied, audit, unavailable, empty text and the `error` field; every tool result the logs keep (native-mcp, custom-toolbox, custom-lightdash) scanned for errors and refusals.
- check 4: every ambiguous turn split by the scoring path (every meaning carried, or `ASKS_WHICH` only) and re-checked with the extra date forms stripped.

## Headline

- Confirmed runs to redact: 208 (frozen 176, hard v1 32, hard-v2 0 new): 121 chance carries, 86 scorer misses, 1 infrastructure failure.
- Chance carries concentrate in the cases the audits already want retired: `bet_wetter_day_nl_orders` 63, `bet_median_days_to_hire` 15, `bet_peak_checkout_hour` 7; 19 cases carried at least one; 16 of them are audit defects or doubts, and the other three (`view_to_cart_rate`, `bet_sessions_per_order`, `bet_weekday_avg_spend`) are answers that named the right number and rejected it.
- Scorer misses are almost all two parser gaps, number words ("Nine distinct customers…", "Three calls…", "Half of…") and whole percentages ("about 33%", "67%", "36%", "158 EUR"); they hit the arms whose models write in prose (custom-hybrid, custom-metricflow, native-mcp and baseline on Haiku) and turn right answers into confident-wrong.
- The `ASKS_WHICH` loophole never fired: of 531 ambiguous turns, none was scored right through a question alone; every right one carried every meaning, and 3 of those carried one meaning only through a date.
- Infrastructure: one empty answer scored wrong; the only other failure (a model-call error row) was already superseded by its rerun; the native-mcp guard's refused queries never ended a run.
- Two scorer problems outside the six checks matter for the confident-wrong rate and the define turns: 78 confident-wrong turns hold decline wording the decline regex misses ("The semantic layer has no median order value metric…"; 44 of them cc-metricflow on the hard set; a sample of 10, read, were all declines listing the closest metrics' numbers), and 37 define turns (read) that state the definition correctly in their own words are scored wrong, because only a verbatim catalog quote passes.

## Summary per check, arm and model

Columns: flagged = turns the mechanical pass flagged for reading; confirmed = turns I confirmed as misleading because of the test or infrastructure.
Check 4 shows right ambiguous turns and how many of them were right only by a date carry.
Check 5 found one duplicate key (below); check 6 is in its own table.
hard-v2's 181 new-case rows (native-bare, native-context, native-context-bare THINKING, native-kc-max; 183 turns, all scored right) produced no flag of any kind and are left out of this table.

| set | arm | model | 1 infra flagged / confirmed | 2 chance: flagged / confirmed | 3 scorer miss: flagged / confirmed | 4 ambiguous: right / misled | redact runs |
|---|---|---|---|---|---|---|---:|
| frozen | baseline | claude-haiku-5-5 | 0 / 0 | 60 / 18 | 15 / 10 | 3 / 0 | 28 |
| frozen | baseline | nemotron:free | 0 / 0 | 4 / 1 | 0 / 0 | 1 / 1 | 2 |
| frozen | cc-metricflow | cc (fresh-haiku) | 0 / 0 | 23 / 8 | 1 / 1 | 5 / 0 | 9 |
| frozen | cc-metricflow | cc (fresh-opus) | 0 / 0 | 4 / 1 | 0 / 0 | 1 / 0 | 1 |
| frozen | cc-metricflow | cc (fresh-sonnet) | 0 / 0 | 22 / 7 | 1 / 0 | 5 / 0 | 7 |
| frozen | cc-metricflow | cc (haiku) | 0 / 0 | 3 / 1 | 0 / 0 | 2 / 0 | 1 |
| frozen | cc-metricflow | cc (opus) | 0 / 0 | 4 / 1 | 0 / 0 | 2 / 0 | 1 |
| frozen | cc-metricflow | cc (sonnet) | 0 / 0 | 3 / 1 | 0 / 0 | 2 / 0 | 1 |
| frozen | cc-metricflow | cc (subject-haiku) | 0 / 0 | 7 / 1 | 0 / 0 | 2 / 0 | 1 |
| frozen | custom-hybrid | claude-haiku-5-5 | 1 / 0 | 67 / 3 | 14 / 12 | 6 / 2 | 17 |
| frozen | custom-hybrid | nemotron:free | 1 / 0 | 12 / 2 | 1 / 1 | 2 / 0 | 3 |
| frozen | custom-lightdash | nemotron:free | 0 / 0 | 1 / 0 | 0 / 0 | 0 / 0 | 0 |
| frozen | custom-metricflow | claude-haiku-5-5 | 1 / 0 | 46 / 9 | 8 / 5 | 5 / 0 | 14 |
| frozen | custom-metricflow | claude-opus-5-5 | 0 / 0 | 36 / 8 | 3 / 0 | 6 / 0 | 8 |
| frozen | custom-metricflow | claude-sonnet-5-5 | 0 / 0 | 27 / 4 | 8 / 3 | 6 / 0 | 7 |
| frozen | custom-metricflow | nemotron:free | 0 / 0 | 11 / 1 | 0 / 0 | 2 / 0 | 1 |
| frozen | custom-toolbox | claude-haiku-5-5 | 0 / 0 | 38 / 5 | 5 / 4 | 0 / 0 | 9 |
| frozen | custom-toolbox | claude-sonnet-5-5 | 0 / 0 | 47 / 3 | 4 / 3 | 0 / 0 | 6 |
| frozen | custom-toolbox | nemotron:free | 0 / 0 | 7 / 1 | 0 / 0 | 0 / 0 | 1 |
| frozen | native-bare | gda (MODEL_UNSPECIFIED) | 0 / 0 | 57 / 3 | 0 / 0 | 2 / 0 | 3 |
| frozen | native-context | gda (MODEL_UNSPECIFIED) | 0 / 0 | 52 / 3 | 1 / 1 | 6 / 0 | 4 |
| frozen | native-context-bare | gda (LATEST_GA_MODEL) | 0 / 0 | 57 / 3 | 2 / 2 | 6 / 0 | 5 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED) | 0 / 0 | 54 / 3 | 2 / 2 | 6 / 0 | 5 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | 0 / 0 | 54 / 3 | 0 / 0 | 6 / 0 | 3 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | 1 / 1 | 55 / 3 | 1 / 1 | 6 / 0 | 5 |
| frozen | native-governed | gda (MODEL_UNSPECIFIED) | 0 / 0 | 18 / 5 | 0 / 0 | 6 / 0 | 5 |
| frozen | native-graph | gda (MODEL_UNSPECIFIED) | 0 / 0 | 42 / 4 | 3 / 0 | 3 / 0 | 4 |
| frozen | native-kc | gda (MODEL_UNSPECIFIED) | 0 / 0 | 40 / 4 | 2 / 0 | 2 / 0 | 4 |
| frozen | native-kc-max | gda (MODEL_UNSPECIFIED) | 0 / 0 | 60 / 3 | 0 / 0 | 4 / 0 | 3 |
| frozen | native-kc-reach | gda (MODEL_UNSPECIFIED) | 0 / 0 | 58 / 3 | 0 / 0 | 1 / 0 | 3 |
| frozen | native-mcp | claude-haiku-5-5 | 51 / 0 | 44 / 1 | 11 / 10 | 4 / 0 | 11 |
| frozen | native-mcp | claude-sonnet-5-5 | 12 / 0 | 70 / 0 | 1 / 0 | 6 / 0 | 0 |
| frozen | native-mcp | nemotron:free | 12 / 0 | 11 / 0 | 1 / 1 | 1 / 0 | 1 |
| frozen | native-shaped | gda (MODEL_UNSPECIFIED) | 0 / 0 | 47 / 3 | 2 / 0 | 0 / 0 | 3 |
| hard | baseline | claude-haiku-5-5 | 0 / 0 | 20 / 2 | 10 / 5 | 3 / 0 | 7 |
| hard | cc-metricflow | cc (fresh-haiku) | 0 / 0 | 13 / 0 | 6 / 5 | 6 / 0 | 5 |
| hard | cc-metricflow | cc (fresh-opus) | 0 / 0 | 4 / 0 | 3 / 0 | 2 / 0 | 0 |
| hard | cc-metricflow | cc (fresh-sonnet) | 0 / 0 | 12 / 0 | 4 / 0 | 6 / 0 | 0 |
| hard | cc-metricflow | cc (haiku) | 0 / 0 | 2 / 0 | 1 / 0 | 2 / 0 | 0 |
| hard | cc-metricflow | cc (opus) | 0 / 0 | 3 / 0 | 2 / 0 | 3 / 0 | 0 |
| hard | cc-metricflow | cc (sonnet) | 0 / 0 | 6 / 0 | 2 / 0 | 3 / 0 | 0 |
| hard | custom-hybrid | claude-haiku-5-5 | 3 / 0 | 32 / 0 | 4 / 4 | 6 / 0 | 4 |
| hard | custom-hybrid | nemotron:free | 0 / 0 | 7 / 0 | 0 / 0 | 2 / 0 | 0 |
| hard | custom-metricflow | claude-haiku-5-5 | 0 / 0 | 28 / 0 | 9 / 9 | 6 / 0 | 9 |
| hard | custom-metricflow | claude-sonnet-5-5 | 0 / 0 | 22 / 0 | 6 / 0 | 6 / 0 | 0 |
| hard | custom-metricflow | nemotron:free | 0 / 0 | 14 / 0 | 4 / 3 | 5 / 0 | 3 |
| hard | custom-toolbox | claude-haiku-5-5 | 0 / 0 | 21 / 0 | 1 / 0 | 0 / 0 | 0 |
| hard | custom-toolbox | claude-sonnet-5-5 | 0 / 0 | 30 / 0 | 0 / 0 | 3 / 0 | 0 |
| hard | custom-toolbox | nemotron:free | 0 / 0 | 2 / 0 | 0 / 0 | 0 / 0 | 0 |
| hard | native-bare | gda (MODEL_UNSPECIFIED) | 0 / 0 | 12 / 0 | 0 / 0 | 4 / 0 | 0 |
| hard | native-context | gda (MODEL_UNSPECIFIED) | 0 / 0 | 21 / 0 | 0 / 0 | 5 / 0 | 0 |
| hard | native-context-bare | gda (LATEST_GA_MODEL) | 0 / 0 | 15 / 0 | 0 / 0 | 7 / 0 | 0 |
| hard | native-context-bare | gda (MODEL_UNSPECIFIED) | 0 / 0 | 14 / 0 | 0 / 0 | 6 / 0 | 0 |
| hard | native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | 0 / 0 | 24 / 0 | 0 / 0 | 8 / 0 | 0 |
| hard | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | 0 / 0 | 16 / 0 | 0 / 0 | 8 / 0 | 0 |
| hard | native-governed | gda (MODEL_UNSPECIFIED) | 0 / 0 | 5 / 0 | 0 / 0 | 7 / 0 | 0 |
| hard | native-graph | gda (MODEL_UNSPECIFIED) | 0 / 0 | 9 / 0 | 3 / 0 | 2 / 0 | 0 |
| hard | native-kc | gda (MODEL_UNSPECIFIED) | 0 / 0 | 7 / 0 | 3 / 0 | 4 / 0 | 0 |
| hard | native-kc-max | gda (MODEL_UNSPECIFIED) | 0 / 0 | 11 / 0 | 0 / 0 | 1 / 0 | 0 |
| hard | native-kc-reach | gda (MODEL_UNSPECIFIED) | 0 / 0 | 16 / 0 | 0 / 0 | 6 / 0 | 0 |
| hard | native-mcp | claude-haiku-5-5 | 30 / 0 | 31 / 0 | 4 / 4 | 3 / 0 | 4 |
| hard | native-mcp | claude-sonnet-5-5 | 2 / 0 | 32 / 0 | 0 / 0 | 2 / 0 | 0 |
| hard | native-mcp | nemotron:free | 8 / 0 | 9 / 0 | 0 / 0 | 2 / 0 | 0 |
| hard | native-shaped | gda (MODEL_UNSPECIFIED) | 0 / 0 | 14 / 0 | 3 / 0 | 0 / 0 | 0 |

## Check 1: infrastructure failures scored as answers

| set | arm | model | case | run | at | finding | verdict |
|---|---|---|---|---:|---|---|---|
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | returns_one_day | 3 | 2026-11-04T21:58:20Z | empty answer text, no tool call, `model_calls` 1, scored wrong | confirmed: redact and rerun |
| frozen | custom-hybrid | nemotron:free | calls_about_returns | 1 | 2026-11-05T00:11:24Z | row with `error`: "the model call failed (… OpenrouterException … TransferEncodingError …)" and no turns | already handled: rerun at 2026-11-05T00:15:42Z (right) is the row `finished` keeps; no action |

Flagged and not confirmed (the recorded outcome does not rest on the failure):
- native-mcp: the guard refused queries in 75 frozen turns (haiku 51, sonnet 12, nemotron 12; 105 refusals) and 40 hard turns (haiku 30, sonnet 2, nemotron 8; 61 refusals), almost all "the dry run refused the query: {}" plus a few "would process 20971520 bytes, over 10485760".
  The `{}` is the probe's own guard (`probes/328_mcp_agent.py`, `_payload`) swallowing the dry run's error text, so the agent never sees why its SQL failed.
  In every one of these turns a later query succeeded and the answer is a substantive answer; outcomes: frozen 63 right, 6 confident-wrong, 4 wrong, 2 unclear; hard 34 right, 4 wrong, 2 confident-wrong.
  Not a redaction, but worth a guard fix (pass the dry run's error message through).
- native-mcp also logged catalog-tool errors (`search_entries` refused as INVALID_ARGUMENT 146 times, "Not found: Dataset pplk8s-lab-001:pplk8s", one "An internal error has occurred"); all recovered within the turn.
- custom-hybrid haiku: "denied access to the silver schema" (frozen 1, hard 3 turns): by design, `agent_sql` reads gold, exposed and legacy only (`hybrid.py`); a reach limit, not a failure.
- custom-metricflow haiku `engaged_customers_week` run 2: "the weekly engaged-customers metric returned an error", answered from the acting-customers metric, right with 9 (genuine).
- cc-metricflow: its answers keep the freshness statement in the text ("Late: … ready only up to 2026-10-03T00:00Z, older than its 36 h deadline"), which the other arms' harness strips; the scorer parses `00` from `T00:00Z` and `36` from "36 h".
  It produced one chance carry (`bet_median_days_lead_to_booking`, counted under check 2) and no other effect I could find.
- No answer in any arm mentions a quota, a rate limit, a timeout or an unwritten audit row; the Opus pass that once answered "the audit record could not be written" is not in the logs any more.

## Check 2: false right (chance carries)

Confirmed chance carries, by kind:
- refuses the asked figure and gives another that the fixture makes equal: `bet_wetter_day_nl_orders` 63 (cannot compare precipitation, lists NL orders for both days, both 3), `bet_median_days_to_hire` 15 ("no median metric; the closest, an average, is 6.08"; median of two hires = mean), `bet_customers_over_three_orders` 2 and `bet_customers_september` 2 (baseline: "can't answer; customer_lifetime lists 10"), `hard_customer_base_turkey` 2 (baseline: all-time TR records 5).
- declines and states a count of something else: `bet_peak_checkout_hour` 7 (total checkouts 2), `bet_median_days_to_interview` 3 (2 candidates at interview), `bet_most_email_opens` 2 ("1 on 1 October"), `page_views_one_day` 2 (5 site sessions), `calls_about_returns` 1 (3 product returns), `bet_weekday_avg_spend` 1 (one Thursday's spend, 215), `engaged_customers_week` 3 (per-day ordering counts 4, 3, 4, 4, 9, 9), `bet_median_days_lead_to_booking` 2 ("0 to 3 booked leads per day"; legacy counts of 0).
- number from a quoted definition or a date the scorer does not strip: `lead_to_booking_rate` 2 ("within 30 days", the per-day rates 33.3% and 25% are the answer), `bet_p75_reply_hours` 1 ("2026‑10‑03" with non-breaking hyphens gives 10), `bet_median_days_lead_to_booking` 1 (`T00:00Z`), `ambiguous_customers` 3 ("1–30 Sept" supplies 30; "2026‑09‑30" supplies 9 and 30).
- main figure differs, the expected one named and rejected: `customers_to_date` 4 (main 10 by a first-order proxy, "out of 30 in the customer table"), `view_to_cart_rate` 3 (main 60%, "the stored view_to_cart_rate shows 0.8, but it doesn't match"), `bet_sessions_per_order` 2 (main 0.21, "0.09 … understates it").

Unclear right turns (111, not redacted) are two-reading answers that label both figures, mostly data agents and toolbox answers that lead with the incl.-cancelled figure ("total order revenue €1,007.15 (€868.65 excluding cancelled orders)"), and toolbox/baseline answers given by channel for a campaign question (one campaign per channel in the fixture).

Audit risks that did not happen in any run (each checked across every right turn of the case): `partners_engaged_one_day` "Oct 2" (no answer wrote the date that way), `page_views_one_day` "4 views by customers 1, 2, 3, 5", `engaged_customers_week` "customers 1…10", `amsterdam_temperature` climate norm (all 15 right answers read 11.0 °C from `gold.daily_weather`), `hard_cost_per_booking_rise` "Sep 21–27" (every right answer names social and +€27.00), `hard_orders_last_fiscal_quarter` (no calendar-Q3 answer also stated 217), `bet_median_days_to_return` and `bet_median_days_lead_to_booking` "10:00" (the date-only scan found only the one `T00:00Z` case), `hard_active_customers_week` WAU/MAU collision, `hv2_signups_never_ordered` IDs (all 12 right answers say "16 customers").

## Check 3: false not-right (scorer misses)

86 confirmed scorer misses, all single-turn cases:
- number words at the headline, scored confident-wrong because another number follows: `calls_about_returns` 8 ("Three customer calls … out of 9 calls labelled"), `signups_september` 5 ("Nine new customers signed up"), `active_customers` 4, `bet_customers_september` 3 and `bet_customers_over_three_orders` 2 ("Ten …"), `orders_over_100` 2 ("Six orders"), `partners_engaged_one_day` 2 ("Two partners"), `damaged_return_share` 1 and `bet_top_return_reason_share` 1 and `hard_replies_within_12_hours` 1 ("Half", "about half").
- whole percentages or whole numbers within half a unit: `hard_candidates_still_in_running` 14 ("33%"), `hard_august_signups_bought` 8 ("36%"), `bookings_wow_growth` 8 ("about 27%"), `bet_p90_order` 7 ("158 EUR", also the nearest-rank reading), `hard_repeat_rate_october` 4 ("59%"), `objection_rate` 4, `outreach_reply_rate` 4, `bet_applicants_reaching_interview` 3 ("About 67% (2 of 3)"; this case's expected_sql is itself defective), `signup_to_first_order_rate` 2, `hard_budget_pacing` 1.
- a share given as a fraction: `hard_repeat_rate_october` 2 ("the repeat share is 10 of 17").

48 genuine misses (the flagged form was incidental: "36 h deadline", "two inputs", 0% answers, calendar-quarter answers, a rejected €717) and 17 unclear (answers that give "4 of 11" or "2 of 6" and decline the ratio, and `bet_applicants_reaching_interview` "between 67% and 100%" or "at least 67%").
Audit risks that did not happen: "6%" for `hard_ad_spend_wow` (every answer wrote 6.0% or 6.01%), "6 days" for `time_to_hire` and `bet_median_days_to_hire`, ROAS as "2,056%" (always paired with 20.56x), "−2,175" for `hv2_search_budget_left_drop`, locale formats.

Outside the six checks, two more scorer misjudgements (not in the redaction list; a scorer change fixes them for every arm on read):
- Decline wording missed: `DECLINE`'s `no (?:such |\w+ )?metric` allows one word before "metric", so "has no median order value metric" or "has no revenue-per-session metric" is not a decline; with the closest metrics' numbers beside it the turn is confident-wrong, and `HEDGE_LIKE` does not send it to the judge.
  Turns: hard cc-metricflow 44 of its 60 confident-wrong, custom-metricflow 10 of 26; frozen cc-metricflow 13 of 33, custom-metricflow 7 of 16, baseline 2, custom-toolbox 1, native-mcp 1 (78 in all; a sample of 10 read, all declines).
- `define` turns: of 108 scored wrong (`followup_how_computed`, `followup_rate_how_computed`, all arms without the catalog text), 37 state the definition correctly in their own words ("net revenue is revenue minus partner returns: €981.69 − €17.50 = €964.19"; "cancelled orders divided by total orders placed"); only verbatim catalog quotes pass, so the 49 right ones are all metric arms quoting the catalog.

## Check 4: ambiguous turns

- 531 ambiguous turns (frozen 157, hard 374); 227 right.
- Right through `ASKS_WHICH` alone: 0 in every arm, model and set; only one ambiguous answer in all the logs contains a sentence `ASKS_WHICH` matches (hard cc-metricflow opus run 1, `hard_ambiguous_q3`: "…; which did you mean?"), and it also gives both meanings, so the loophole the audits found was never exercised.
- Every right turn carries each meaning's number; 3 carry one meaning only through a date and are chance carries (custom-hybrid haiku `ambiguous_customers` runs 1 and 3 state "Customers to date: 9", with 30 coming from "1–30 Sept"; baseline nemotron run 1 gives only 10, with 9 and 30 from "2026‑09‑30").
- The 304 not-right turns are silent picks of one meaning (or two of three for `ambiguous_customers`), 21 of them with a "let me know if you meant …" offer and no question, or no meaning at all; I found no answer that asked which meaning and was scored wrong.

## Check 5: duplicates

One key appears twice in one log: `eval-local.jsonl`, custom-hybrid, nemotron:free, `calls_about_returns`, run 1: an `error` row at 2026-11-05T00:11:24Z and a scored row (right) at 2026-11-05T00:15:42Z.
`bet_eval.finished` keeps the scored row (a scored row overwrites; one error alone never finishes a run), and so does every read through `read_logs`.
No other key repeats within a log, across a set's logs, or between a hard-v2 carried row and its v1 row other than as the intended copy.

## Check 6: runs of defect cases (expected_sql, readings, fixture)

Defect cases counted (category column of the four audits): frozen `amsterdam_temperature`, `time_to_hire`, `bookings_wow_growth`, `ambiguous_customers`, `bet_customers_september`, `bet_weekday_most_orders`, `bet_median_session_minutes`, `bet_peak_page_view_hour`, `bet_applicants_reaching_interview`, `bet_median_days_to_hire`, `bet_istanbul_warmer`, `bet_delivery_calls_per_100_shipped`, `bet_customers_over_three_orders`, `bet_median_days_lead_to_booking`, `bet_most_email_opens`, `bet_p75_reply_hours`, `bet_median_days_to_interview`, `bet_wetter_day_nl_orders`; hard v1 `hard_happiest_call_topic`; hard-v2 new `hv2_first_order_value_october`.
Doubts in those classes: frozen `returns_amount`, `median_order_value`, `customers_to_date`, `bet_p90_order`; hard v1 `hard_fiscal_ytd_net_revenue`, `hard_refund_rate_by_value`; hard-v2 new `hv2_median_gap_between_orders`, `hv2_median_customer_spend`.
Run rows (error rows excluded; hard-v2 counts only its new-case rows):

| arm | frozen (18 cases) | hard v1 (1 case) | hard-v2 new (1 case) |
|---|---:|---:|---:|
| baseline | 58 | 3 | 0 |
| cc-metricflow | 191 | 10 | 0 |
| custom-hybrid | 72 | 4 | 0 |
| custom-lightdash | 1 | 0 | 0 |
| custom-metricflow | 180 | 9 | 0 |
| custom-toolbox | 126 | 7 | 0 |
| native-bare | 54 | 3 | 3 |
| native-context | 54 | 3 | 3 |
| native-context-bare | 216 | 11 | 3 |
| native-governed | 54 | 3 | 0 |
| native-graph | 54 | 3 | 0 |
| native-kc | 54 | 3 | 0 |
| native-kc-max | 54 | 3 | 3 |
| native-kc-reach | 54 | 3 | 0 |
| native-mcp | 126 | 6 | 0 |
| native-shaped | 54 | 3 | 0 |

Doubts in the same classes (not defects; counted the same way):

| arm | frozen doubts (4 cases) | hard v1 doubts (2) | hard-v2 new doubts (2) |
|---|---:|---:|---:|
| baseline | 15 | 6 | 0 |
| cc-metricflow | 43 | 20 | 0 |
| custom-hybrid | 16 | 8 | 0 |
| custom-lightdash | 3 | 0 | 0 |
| custom-metricflow | 41 | 18 | 0 |
| custom-toolbox | 28 | 14 | 0 |
| native-bare | 12 | 6 | 6 |
| native-context | 12 | 6 | 6 |
| native-context-bare | 48 | 24 | 6 |
| native-governed | 12 | 6 | 0 |
| native-graph | 12 | 6 | 0 |
| native-kc | 12 | 6 | 0 |
| native-kc-max | 12 | 6 | 6 |
| native-kc-reach | 12 | 6 | 0 |
| native-mcp | 28 | 12 | 0 |
| native-shaped | 12 | 6 | 0 |

## Per case: right runs, chance carries, scorer misses

Cases listed: every case with a chance carry, an unclear right turn or a scorer miss, plus every case an audit flagged with a scorer risk or with an expected whole number of 40 or less.

| set | case | turns | right | chance | unclear (right) | scorer miss | genuine miss | did a run actually mislead? |
|---|---|---:|---:|---:|---:|---:|---:|---|
| frozen | active_customers | 81 | 71 | 0 | 1 | 4 | 0 | yes |
| frozen | ambiguous_customers | 78 | 54 | 3 | 0 | 0 | 0 | yes |
| frozen | ambiguous_sales | 158 | 125 | 0 | 1 | 0 | 0 | no |
| frozen | amsterdam_temperature | 80 | 15 | 0 | 0 | 0 | 0 | no |
| frozen | average_order_value | 79 | 66 | 0 | 9 | 0 | 0 | no |
| frozen | bet_applicants_reaching_interview | 78 | 31 | 0 | 0 | 3 | 0 | yes |
| frozen | bet_cart_to_checkout_minutes | 77 | 20 | 0 | 0 | 0 | 0 | no |
| frozen | bet_customers_over_three_orders | 78 | 53 | 2 | 0 | 2 | 0 | yes |
| frozen | bet_customers_september | 77 | 63 | 2 | 0 | 3 | 0 | yes |
| frozen | bet_delivery_calls_per_100_shipped | 77 | 43 | 0 | 0 | 0 | 5 | no |
| frozen | bet_istanbul_warmer | 78 | 14 | 0 | 0 | 0 | 0 | no |
| frozen | bet_median_days_lead_to_booking | 78 | 37 | 3 | 1 | 0 | 0 | yes |
| frozen | bet_median_days_to_hire | 77 | 43 | 15 | 0 | 0 | 0 | yes |
| frozen | bet_median_days_to_interview | 77 | 29 | 3 | 24 | 0 | 0 | yes |
| frozen | bet_median_days_to_return | 77 | 41 | 0 | 0 | 0 | 0 | no |
| frozen | bet_median_order_september | 77 | 22 | 0 | 1 | 0 | 0 | no |
| frozen | bet_median_reply_hours | 77 | 21 | 0 | 1 | 0 | 0 | no |
| frozen | bet_median_session_minutes | 78 | 15 | 0 | 3 | 0 | 0 | no |
| frozen | bet_median_signup_to_first_order | 77 | 40 | 0 | 0 | 0 | 0 | no |
| frozen | bet_most_email_opens | 78 | 56 | 2 | 0 | 0 | 1 | yes |
| frozen | bet_p75_reply_hours | 78 | 23 | 1 | 0 | 0 | 0 | yes |
| frozen | bet_p90_order | 78 | 29 | 0 | 1 | 7 | 0 | yes |
| frozen | bet_peak_checkout_hour | 77 | 38 | 7 | 0 | 0 | 0 | yes |
| frozen | bet_peak_page_view_hour | 77 | 31 | 0 | 0 | 0 | 0 | no |
| frozen | bet_sessions_per_order | 77 | 42 | 2 | 0 | 0 | 0 | yes |
| frozen | bet_top_call_topic | 77 | 61 | 0 | 0 | 0 | 0 | no |
| frozen | bet_top_campaign_spend | 77 | 73 | 0 | 6 | 0 | 0 | no |
| frozen | bet_top_return_reason_share | 77 | 60 | 0 | 0 | 1 | 0 | yes |
| frozen | bet_weekday_avg_spend | 78 | 64 | 1 | 0 | 0 | 0 | yes |
| frozen | bet_weekday_most_orders | 78 | 75 | 0 | 1 | 0 | 0 | no |
| frozen | bet_wetter_day_nl_orders | 78 | 77 | 63 | 0 | 0 | 0 | yes |
| frozen | bookings_wow_growth | 79 | 69 | 0 | 0 | 8 | 0 | yes |
| frozen | calls_about_returns | 79 | 56 | 1 | 0 | 8 | 0 | yes |
| frozen | cancellation_rate | 80 | 79 | 0 | 0 | 0 | 0 | no |
| frozen | cancelled_total | 80 | 77 | 0 | 0 | 0 | 0 | no |
| frozen | candidates_in_interview_as_of | 79 | 62 | 0 | 0 | 0 | 0 | no |
| frozen | customers_to_date | 80 | 71 | 4 | 0 | 0 | 0 | yes |
| frozen | damaged_return_share | 80 | 75 | 0 | 0 | 1 | 0 | yes |
| frozen | engaged_customers_week | 79 | 66 | 3 | 0 | 0 | 0 | yes |
| frozen | followup_day_before | 158 | 153 | 0 | 4 | 0 | 0 | no |
| frozen | followup_how_computed | 158 | 100 | 0 | 1 | 0 | 0 | no |
| frozen | followup_rate_how_computed | 156 | 102 | 0 | 0 | 0 | 0 | no |
| frozen | followup_switch_metric | 156 | 149 | 0 | 0 | 0 | 0 | no |
| frozen | lead_to_booking_rate | 79 | 77 | 2 | 0 | 0 | 0 | yes |
| frozen | leads_wow_growth | 78 | 78 | 0 | 0 | 0 | 0 | no |
| frozen | monthly_active_customers | 80 | 71 | 0 | 0 | 0 | 0 | no |
| frozen | objection_rate | 78 | 57 | 0 | 0 | 4 | 0 | yes |
| frozen | orders_one_day | 81 | 81 | 0 | 0 | 0 | 0 | no |
| frozen | orders_over_100 | 79 | 60 | 0 | 1 | 2 | 0 | yes |
| frozen | outreach_messages_sent | 79 | 63 | 0 | 0 | 0 | 0 | no |
| frozen | outreach_reply_rate | 80 | 60 | 0 | 0 | 4 | 0 | yes |
| frozen | page_views_one_day | 80 | 61 | 2 | 0 | 0 | 0 | yes |
| frozen | partners_engaged_one_day | 80 | 62 | 0 | 0 | 2 | 0 | yes |
| frozen | planted_campaign_least_spend | 78 | 73 | 0 | 3 | 0 | 0 | no |
| frozen | planted_campaign_top_spend | 78 | 77 | 0 | 6 | 0 | 0 | no |
| frozen | planted_top_customer | 77 | 58 | 0 | 1 | 0 | 0 | no |
| frozen | repeat_revenue_share | 79 | 63 | 0 | 0 | 0 | 0 | no |
| frozen | return_rate_september | 80 | 69 | 0 | 0 | 0 | 3 | no |
| frozen | returns_one_day | 81 | 78 | 0 | 0 | 0 | 0 | no |
| frozen | revenue_best_day | 81 | 80 | 0 | 2 | 0 | 0 | no |
| frozen | revenue_fiscal_q3 | 80 | 58 | 0 | 2 | 0 | 10 | no |
| frozen | revenue_mtd | 78 | 76 | 0 | 2 | 0 | 0 | no |
| frozen | revenue_one_day | 81 | 80 | 0 | 4 | 0 | 0 | no |
| frozen | revenue_wow_growth | 79 | 74 | 0 | 1 | 0 | 0 | no |
| frozen | signup_to_first_order_rate | 80 | 66 | 0 | 0 | 2 | 0 | yes |
| frozen | signups_september | 79 | 63 | 0 | 0 | 5 | 0 | yes |
| frozen | time_to_hire | 78 | 62 | 0 | 0 | 0 | 0 | no |
| frozen | top_campaigns_by_spend | 79 | 79 | 0 | 11 | 0 | 0 | no |
| frozen | view_to_cart_rate | 79 | 53 | 3 | 0 | 0 | 0 | yes |
| hard-v2 | hv2_median_gap_between_orders | 12 | 12 | 0 | 0 | 0 | 0 | no |
| hard-v2 | hv2_revenue_share_unreturned_orders | 12 | 12 | 0 | 0 | 0 | 0 | no |
| hard-v2 | hv2_search_budget_left_drop | 12 | 12 | 0 | 0 | 0 | 0 | no |
| hard-v2 | hv2_signups_never_ordered | 12 | 12 | 0 | 0 | 0 | 0 | no |
| hard-v2 | hv2_spend_on_days_without_email_booking | 12 | 12 | 0 | 1 | 0 | 0 | no |
| hard-v2 | hv2_top_three_customers_share | 12 | 12 | 0 | 0 | 0 | 0 | no |
| hard | hard_active_customers_week | 75 | 3 | 0 | 0 | 0 | 0 | no |
| hard | hard_ad_spend_wow | 75 | 61 | 0 | 0 | 0 | 0 | no |
| hard | hard_aov_last_month | 76 | 67 | 0 | 9 | 0 | 0 | no |
| hard | hard_august_signups_bought | 75 | 42 | 0 | 0 | 8 | 6 | yes |
| hard | hard_average_order_rise | 75 | 49 | 0 | 1 | 0 | 0 | no |
| hard | hard_basket_size_week | 75 | 60 | 0 | 4 | 0 | 0 | no |
| hard | hard_best_week | 74 | 70 | 0 | 1 | 0 | 0 | no |
| hard | hard_budget_pacing | 75 | 42 | 0 | 0 | 1 | 0 | yes |
| hard | hard_candidates_still_in_running | 75 | 29 | 0 | 3 | 14 | 4 | yes |
| hard | hard_cost_per_booking_rise | 75 | 72 | 0 | 0 | 0 | 0 | no |
| hard | hard_customer_base_turkey | 75 | 67 | 2 | 1 | 0 | 0 | yes |
| hard | hard_followup_cancelling_country | 150 | 130 | 0 | 0 | 0 | 0 | no |
| hard | hard_mqls_social_september | 75 | 66 | 0 | 0 | 0 | 0 | no |
| hard | hard_orders_last_fiscal_quarter | 75 | 56 | 0 | 0 | 0 | 13 | no |
| hard | hard_refund_rate_by_value | 75 | 39 | 0 | 3 | 0 | 4 | no |
| hard | hard_repeat_rate_october | 75 | 45 | 0 | 0 | 6 | 0 | yes |
| hard | hard_replies_within_12_hours | 75 | 29 | 0 | 0 | 1 | 0 | yes |
| hard | hard_revenue_per_buyer_country | 75 | 42 | 0 | 1 | 0 | 0 | no |
| hard | hard_roas_september | 75 | 50 | 0 | 0 | 0 | 0 | no |
| hard | hard_runner_up_channel_leads | 75 | 75 | 0 | 0 | 0 | 0 | no |
| hard | hard_top_channel_bookings | 75 | 75 | 0 | 0 | 0 | 0 | no |

## Run keys to redact

All 208 rows are also in `/tmp/claude-0/hv2/audit/redact-candidates.jsonl` (`{"kind":"run","arm","model","case","run","at","set","reason","evidence"}`).
Classes: `infra` (1), `chance` (121; a rerun is the fix), `scorer_miss` (86; the scorer fixes below remove the need, and a rerun would likely repeat the same wording).
Each v1 key also removes its carried hard-v2 copy (same `at`).
The bet_median_days_to_hire and bet_wetter_day_nl_orders rows (78) become moot if those cases are retired.

| set | arm | model | case | run | at | class | reason | evidence |
|---|---|---|---|---:|---|---|---|---|
| frozen | baseline | nemotron:free | ambiguous_customers | 1 | 2026-11-06T02:37:30Z | chance | one meaning (10) only; 9 and 30 come from the date 2026‑09‑30 written with non-breaking hyphens | "we had 10 customers ... (first order on or before 2026‑09‑30 ...)" |
| frozen | custom-hybrid | claude-haiku-5-5 | ambiguous_customers | 1 | 2026-11-04T18:32:47Z | chance | customers-to-date given as 9; the 30 meaning is carried only by the date range '1–30 Sept' | "(1–30 Sept) ... Customers to date (everyone signed up by each day, running total): 9" |
| frozen | custom-hybrid | claude-haiku-5-5 | ambiguous_customers | 3 | 2026-11-04T18:49:38Z | chance | customers-to-date given as 9; 30 carried only by '1–30 Sep' / '30 Sep' | "(1–30 Sep) ... Customers to date (everyone signed up by 30 Sep 2026, running total): 9" |
| frozen | baseline | claude-haiku-5-5 | bet_customers_over_three_orders | 2 | 2026-11-03T21:31:55Z | chance | declines the period; 10 is the lifetime count of customers with >3 orders (fixture: every base customer) | "The closest figure is 10 customers with more than three lifetime orders" |
| frozen | baseline | claude-haiku-5-5 | bet_customers_over_three_orders | 3 | 2026-11-03T21:41:17Z | chance | declines the period; 10 is the lifetime count (fixture constant) | "The closest figure is 10 customers with more than three lifetime orders" |
| frozen | baseline | claude-haiku-5-5 | bet_customers_september | 1 | 2026-11-03T21:21:06Z | chance | declines the count; 10 is customer_lifetime's base-customer count (fixture constant) | "The warehouse can't give an exact count ... `gold.customer_lifetime` lists 10" |
| frozen | baseline | claude-haiku-5-5 | bet_customers_september | 3 | 2026-11-03T21:39:22Z | chance | declines the count; 10 customers with an order span overlapping September (fixture constant) | "The warehouse can't give an exact count ... only 10 customers have a lifetime order span overlapping Sept" |
| frozen | baseline | claude-haiku-5-5 | bet_median_days_lead_to_booking | 1 | 2026-11-03T21:23:30Z | chance | declines; 0 is a daily booked-lead count | "I can't answer this from the warehouse ... 0 to 3 booked leads per day" |
| frozen | cc-metricflow | cc (fresh-sonnet) | bet_median_days_lead_to_booking | 2 | 2026-11-05T00:48:14Z | chance | declines; the only 0 is in the freshness timestamp '2026-10-03T00:00Z' left in the answer text | "The semantic layer has no metric for the median days ... ready only up to 2026-10-03T00:00Z" |
| frozen | native-graph | gda (MODEL_UNSPECIFIED) | bet_median_days_lead_to_booking | 1 | 2026-11-03T15:00:04Z | chance | declines; 0 is the legacy table's daily booking count | "daily aggregated counts of leads and bookings (which are 0 for the recorded days) ... not possible" |
| frozen | cc-metricflow | cc (fresh-haiku) | bet_median_days_to_hire | 1 | 2026-11-04T23:26:49Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median days-to-hire metric; its Time to hire (days) metric is an average of days from applying to being hired, and for candi" |
| frozen | cc-metricflow | cc (fresh-haiku) | bet_median_days_to_hire | 2 | 2026-11-05T00:37:23Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median metric; its closest metric, Time to hire (days), is an average and gives 6.08 days from application to hire for candi" |
| frozen | cc-metricflow | cc (fresh-haiku) | bet_median_days_to_hire | 3 | 2026-11-05T01:04:13Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median time-to-hire metric; the closest is Time to hire (days), which is an average and was 6.08 days for candidates hired 1" |
| frozen | cc-metricflow | cc (fresh-sonnet) | bet_median_days_to_hire | 2 | 2026-11-05T00:48:14Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median time-to-hire metric; the closest is Time to hire (days), which is an average, and it was 6.0833 days for candidates h" |
| frozen | cc-metricflow | cc (fresh-sonnet) | bet_median_days_to_hire | 3 | 2026-11-05T01:14:51Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median time-to-hire metric; the closest is Time to hire (days), which is an average, and it was 6.0833 days for candidates h" |
| frozen | custom-hybrid | claude-haiku-5-5 | bet_median_days_to_hire | 2 | 2026-11-04T18:43:27Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median time-to-hire metric, and I can't compute one from the underlying data because I don't have permission to read the sil" |
| frozen | custom-hybrid | claude-haiku-5-5 | bet_median_days_to_hire | 3 | 2026-11-04T18:51:32Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "Not a governed metric: no metric gives a median. The semantic layer's `time_to_hire_days` is an average, so I took the two September–October 2026 hire" |
| frozen | custom-hybrid | nemotron:free | bet_median_days_to_hire | 1 | 2026-11-05T00:22:42Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "No governed metric defines a median time-to-hire — `time_to_hire_days` measures the average days from applying to being hired (the single definition o" |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_median_days_to_hire | 1 | 2026-11-03T20:49:40Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median time-to-hire metric, so I can't give the median. The closest metric, Time to hire (days), is an average: candidates h" |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_median_days_to_hire | 2 | 2026-11-03T20:56:34Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median time-to-hire metric. Its closest metric, Time to hire (days), is an average: about 6.08 days for candidates hired fro" |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_median_days_to_hire | 3 | 2026-11-03T21:03:28Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median time-to-hire metric. The closest is Time to hire (days), which is an average: candidates hired in September and Octob" |
| frozen | custom-metricflow | claude-opus-5-5 | bet_median_days_to_hire | 1 | 2026-11-04T18:39:07Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median time-to-hire metric. Its only definition is **Time to hire (days)**, which is an average. By that measure, the 2 cand" |
| frozen | custom-metricflow | claude-opus-5-5 | bet_median_days_to_hire | 2 | 2026-11-04T18:51:45Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "I can't give you the median: the semantic layer has no median time-to-hire metric. The closest one is **Time to hire (days)**, which is an average. Fo" |
| frozen | custom-metricflow | claude-opus-5-5 | bet_median_days_to_hire | 3 | 2026-11-04T19:04:44Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "I can't give you the median: the semantic layer has no median time-to-hire metric. The closest metric is **Time to hire (days)**, which is an average." |
| frozen | custom-metricflow | claude-sonnet-5-5 | bet_median_days_to_hire | 1 | 2026-11-03T21:51:02Z | chance | refuses the median and gives the governed mean; equal only because the fixture has two hires (median of two = mean) | "The semantic layer has no median time-to-hire metric. The closest is "Time to hire (days)", which is an average, so I can't give you a median. For can" |
| frozen | baseline | claude-haiku-5-5 | bet_median_days_to_interview | 1 | 2026-11-03T21:24:06Z | chance | declines; 2 is the count of candidates at interview | "I can't answer this ... (2 candidates reached interview on 3–4 October 2026)" |
| frozen | baseline | claude-haiku-5-5 | bet_median_days_to_interview | 2 | 2026-11-03T21:33:04Z | chance | declines; 2 is the count of candidates at interview | "The warehouse can't answer this ... there are 2 candidates recorded at the interview stage" |
| frozen | baseline | claude-haiku-5-5 | bet_median_days_to_interview | 3 | 2026-11-03T21:42:32Z | chance | declines; 2 is the count of candidates at interview | "The warehouse can't answer this ... (2 candidates reached interview between 3 and 4 October 2026)" |
| frozen | baseline | claude-haiku-5-5 | bet_most_email_opens | 1 | 2026-11-03T21:23:50Z | chance | declines; 1 is the daily open count on 1 October | "The warehouse can't answer this ... 3 CRM email opens in total (1 on 1 October and 2 on 2 October)" |
| frozen | baseline | claude-haiku-5-5 | bet_most_email_opens | 2 | 2026-11-03T21:32:40Z | chance | declines; 1 is the daily open count on 1 October | "The warehouse can't answer this ... 3 email opens in total (1 on 1 October, 2 on 2 October)" |
| frozen | custom-hybrid | nemotron:free | bet_p75_reply_hours | 1 | 2026-11-05T00:28:03Z | chance | declines with 'no figure can be given'; 10 is parsed from the date 2026‑10‑03 written with non-breaking hyphens | "Not a governed metric: no figure can be given ... sent 2026‑09‑20 through 2026‑10‑03" |
| frozen | cc-metricflow | cc (fresh-haiku) | bet_peak_checkout_hour | 3 | 2026-11-05T01:04:13Z | chance | declines the hour; 2 is the total checkout-session count | "I cannot name the peak checkout hour ... shows 2 checkout sessions" |
| frozen | custom-hybrid | claude-haiku-5-5 | bet_peak_checkout_hour | 1 | 2026-11-04T18:37:02Z | chance | declines the hour; 2 is the total checkout count | "I can't identify the busiest hour ... gives 2 checkout events across 20 September to 3 October" |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_peak_checkout_hour | 1 | 2026-11-03T20:51:04Z | chance | declines the hour; 2 is the total checkout count (equals the peak-hour count by fixture) | "I can't say which hour had the most checkouts. For the period, checkout events total 2" |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_peak_checkout_hour | 2 | 2026-11-03T20:57:57Z | chance | declines the hour; 2 is the total checkout count | "I can't answer the hour question ... there were 2 checkout actions in total" |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_peak_checkout_hour | 3 | 2026-11-03T21:04:44Z | chance | declines the hour; 2 is the total checkout count | "I can't say which hour had the most checkouts ... there were 2 checkout events" |
| frozen | custom-metricflow | claude-opus-5-5 | bet_peak_checkout_hour | 1 | 2026-11-04T18:41:11Z | chance | declines the hour; 2 is the total checkout count | "I can't tell you which hour had the most checkouts ... a count of 2 checkout events" |
| frozen | native-governed | gda (MODEL_UNSPECIFIED) | bet_peak_checkout_hour | 2 | 2026-11-03T20:07:01Z | chance | declines the hour; 2 is the total checkout count | "hourly checkout event breakdowns cannot be determined ... a total of 2 checkout actions across all days" |
| frozen | baseline | claude-haiku-5-5 | bet_sessions_per_order | 2 | 2026-11-03T21:33:30Z | chance | main figure 0.21; 0.09 named and rejected as understated | "about 0.21 sessions per order ... the ratio would be 0.09, but that understates it" |
| frozen | baseline | claude-haiku-5-5 | bet_sessions_per_order | 3 | 2026-11-03T21:42:52Z | chance | main figure 0.21; 0.09 named and rejected | "the ratio is about 0.21 sessions per order. I didn't use the 75 orders ... roughly 0.09" |
| frozen | custom-metricflow | claude-opus-5-5 | bet_weekday_avg_spend | 1 | 2026-11-04T18:40:45Z | chance | declines the average; 215 is one Thursday's daily spend (10 Sept) | "I can't give you an average in EUR ... Thursday's four days were €210 (Sept 3), €215 (Sept 10)" |
| frozen | cc-metricflow | cc (fresh-haiku) | bet_wetter_day_nl_orders | 1 | 2026-11-04T23:26:49Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation or weather metric, so I cannot say which day was wetter, and no metric is close enough to stand in for it. Ord" |
| frozen | cc-metricflow | cc (fresh-haiku) | bet_wetter_day_nl_orders | 2 | 2026-11-05T00:37:23Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation metric, so I cannot say which of the two days was wetter, and no metric in it is close enough to stand in for " |
| frozen | cc-metricflow | cc (fresh-haiku) | bet_wetter_day_nl_orders | 3 | 2026-11-05T01:04:13Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation metric, so I cannot say which day had more rain in Amsterdam; the closest metrics, orders and revenue by custo" |
| frozen | cc-metricflow | cc (fresh-opus) | bet_wetter_day_nl_orders | 1 | 2026-11-05T20:04:01Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation or weather metric, so I cannot say which of 1 or 2 October 2026 was wetter in Amsterdam; the closest metric is" |
| frozen | cc-metricflow | cc (fresh-sonnet) | bet_wetter_day_nl_orders | 1 | 2026-11-04T23:42:57Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation or weather metric, so I cannot say which day was wetter (the closest metrics are only the order metrics, e.g. " |
| frozen | cc-metricflow | cc (fresh-sonnet) | bet_wetter_day_nl_orders | 2 | 2026-11-05T00:48:14Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation or weather metric, so I cannot say which of 1 or 2 October 2026 was wetter; the closest metrics are only order" |
| frozen | cc-metricflow | cc (fresh-sonnet) | bet_wetter_day_nl_orders | 3 | 2026-11-05T01:14:51Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation (weather) metric, so I cannot say which day had more rain; the closest metrics are orders_total (Orders) by cu" |
| frozen | cc-metricflow | cc (haiku) | bet_wetter_day_nl_orders | 1 | 2026-11-04T19:37:57Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation metric, so I cannot say which day was wetter in Amsterdam; for customers in the Netherlands, 3 orders were pla" |
| frozen | cc-metricflow | cc (opus) | bet_wetter_day_nl_orders | 1 | 2026-11-04T19:55:47Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no weather or precipitation metric, so I cannot say which day was wetter in Amsterdam; Orders by customers in the Netherlands (" |
| frozen | cc-metricflow | cc (sonnet) | bet_wetter_day_nl_orders | 1 | 2026-11-04T19:46:45Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation or weather metric, so I cannot say which day was wetter in Amsterdam. Customers in the Netherlands placed 3 or" |
| frozen | cc-metricflow | cc (subject-haiku) | bet_wetter_day_nl_orders | 1 | 2026-11-05T01:28:25Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation metric, so I cannot say which of 1 or 2 October 2026 was wetter in Amsterdam; the closest metric, orders by cu" |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_wetter_day_nl_orders | 1 | 2026-11-03T20:51:18Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation metric, so I can't say which day had more rain in Amsterdam. Customers in the Netherlands placed 3 orders on 1" |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_wetter_day_nl_orders | 2 | 2026-11-03T20:58:09Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Orders from Netherlands customers were 3 on 1 October 2026 and 3 on 2 October 2026, so they tie on that count. I could not compare precipitation in Am" |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_wetter_day_nl_orders | 3 | 2026-11-03T21:04:56Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation metric, so I can't say which day had more rain in Amsterdam. Orders from customers in the Netherlands were 3 o" |
| frozen | custom-metricflow | claude-opus-5-5 | bet_wetter_day_nl_orders | 1 | 2026-11-04T18:41:42Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't tell you which day had more rain in Amsterdam, because the semantic layer has no weather or precipitation metric. The closest metrics are abou" |
| frozen | custom-metricflow | claude-opus-5-5 | bet_wetter_day_nl_orders | 2 | 2026-11-04T18:54:23Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't tell you which day had more rain in Amsterdam, because the semantic layer has no precipitation or weather metric. Customers in the Netherlands" |
| frozen | custom-metricflow | claude-opus-5-5 | bet_wetter_day_nl_orders | 3 | 2026-11-04T19:07:01Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't tell you which day had more rain in Amsterdam, because the semantic layer has no weather or precipitation metric. The closest metrics are abou" |
| frozen | custom-metricflow | claude-sonnet-5-5 | bet_wetter_day_nl_orders | 1 | 2026-11-03T21:52:54Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation or weather metric, so I can't say which of 1 or 2 October 2026 had more rain in Amsterdam. The closest metrics" |
| frozen | custom-metricflow | claude-sonnet-5-5 | bet_wetter_day_nl_orders | 2 | 2026-11-03T22:15:46Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't tell you which of 1 or 2 October 2026 had more precipitation in Amsterdam. The semantic layer has no precipitation or weather metric. The clos" |
| frozen | custom-metricflow | claude-sonnet-5-5 | bet_wetter_day_nl_orders | 3 | 2026-11-03T22:24:28Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't say which of 1 or 2 October 2026 had more precipitation in Amsterdam. The semantic layer has no precipitation or weather metric. The closest m" |
| frozen | custom-metricflow | nemotron:free | bet_wetter_day_nl_orders | 1 | 2026-11-04T00:38:40Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The semantic layer has no precipitation or weather metric for Amsterdam, so I cannot determine which of 1 or 2 October 2026 had more precipitation. Or" |
| frozen | custom-toolbox | claude-haiku-5-5 | bet_wetter_day_nl_orders | 1 | 2026-11-04T17:38:35Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't answer which day had more precipitation in Amsterdam, because none of my tools provide weather data. Customers in the Netherlands placed 3 ord" |
| frozen | custom-toolbox | claude-haiku-5-5 | bet_wetter_day_nl_orders | 2 | 2026-11-04T17:44:46Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't say which day had more precipitation in Amsterdam, because none of my tools provides weather data. Customers in the Netherlands placed 3 order" |
| frozen | custom-toolbox | claude-haiku-5-5 | bet_wetter_day_nl_orders | 3 | 2026-11-04T17:50:58Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't say which day had more precipitation in Amsterdam, because none of my tools provide weather data. On both 1 and 2 October 2026, customers in t" |
| frozen | custom-toolbox | claude-sonnet-5-5 | bet_wetter_day_nl_orders | 1 | 2026-11-04T18:11:40Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't tell you which day had more precipitation in Amsterdam. None of my tools return weather data, so I can't compare 1 and 2 October 2026. I can a" |
| frozen | custom-toolbox | claude-sonnet-5-5 | bet_wetter_day_nl_orders | 2 | 2026-11-04T18:18:52Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't tell you which day had more precipitation in Amsterdam. None of my tools return weather data, so I can't compare 1 and 2 October 2026. Without" |
| frozen | custom-toolbox | claude-sonnet-5-5 | bet_wetter_day_nl_orders | 3 | 2026-11-04T18:26:12Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "I can't tell you which day had more precipitation in Amsterdam. None of my tools return weather data, so I have no precipitation figures for 1 or 2 Oc" |
| frozen | native-bare | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 1 | 2026-11-04T18:41:19Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The database does not contain weather or precipitation data for Amsterdam. However, for both **1 October 2026** and **2 October 2026**, customers in t" |
| frozen | native-bare | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 2 | 2026-11-04T19:00:11Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The available database contains order and customer records, but does not track weather or precipitation data for Amsterdam. For the order activity, cu" |
| frozen | native-bare | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 3 | 2026-11-04T19:20:24Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation and weather data for Amsterdam are not available in the database. However, on both **1 October 2026** and **2 October 2026**, customers " |
| frozen | native-context | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 1 | 2026-11-03T17:01:21Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data for Amsterdam is not available in the dataset. However, customers in the Netherlands (country code 'NL') placed **3** o" |
| frozen | native-context | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 2 | 2026-11-03T20:11:22Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data for Amsterdam is not tracked in the available database. However, on both **1 October 2026** and **2 October 2026**, cus" |
| frozen | native-context | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 3 | 2026-11-03T20:38:11Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data for Amsterdam is not tracked in the database. However, on both **1 October 2026** and **2 October 2026**, customers in " |
| frozen | native-context-bare | gda (LATEST_GA_MODEL) | bet_wetter_day_nl_orders | 1 | 2026-11-04T17:57:36Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data for Amsterdam is not available in the dataset. However, for customers in the Netherlands (NL), exactly 3 orders were pl" |
| frozen | native-context-bare | gda (LATEST_GA_MODEL) | bet_wetter_day_nl_orders | 2 | 2026-11-04T18:18:16Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data for Amsterdam is not available in the database. However, on both **1 October 2026** and **2 October 2026**, customers i" |
| frozen | native-context-bare | gda (LATEST_GA_MODEL) | bet_wetter_day_nl_orders | 3 | 2026-11-04T18:40:13Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data for Amsterdam is not available in the database. However, for both **1 October 2026** and **2 October 2026**, customers " |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 1 | 2026-11-03T20:49:13Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data for Amsterdam is not available in the database. For orders placed by customers in the Netherlands (`country = 'NL'`), e" |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 2 | 2026-11-03T21:07:43Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data for Amsterdam is not available in the database. However, customers in the Netherlands placed **3 orders** on **1 Octobe" |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 3 | 2026-11-03T21:54:57Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation data is not available in the database. However, on both **1 October 2026** and **2 October 2026**, customers in the Netherlands placed e" |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | bet_wetter_day_nl_orders | 1 | 2026-11-04T23:28:00Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The provided database does not contain weather or precipitation data for Amsterdam. However, on both **1 October 2026** and **2 October 2026**, custom" |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | bet_wetter_day_nl_orders | 2 | 2026-11-05T00:01:52Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The database does not contain weather or precipitation data for Amsterdam. However, for orders placed by customers in the Netherlands (`NL`), **3 orde" |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | bet_wetter_day_nl_orders | 3 | 2026-11-05T00:28:09Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The dataset does not contain weather or precipitation data for Amsterdam. However, for orders placed by customers in the Netherlands (NL), **3 orders*" |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | bet_wetter_day_nl_orders | 1 | 2026-11-04T20:55:21Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The available database does not contain weather or precipitation data for Amsterdam. However, for orders placed by customers in the Netherlands (`coun" |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | bet_wetter_day_nl_orders | 2 | 2026-11-04T21:53:05Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The database does not contain weather or precipitation data for Amsterdam. However, for orders placed by customers in the Netherlands (NL): - **1 Octo" |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | bet_wetter_day_nl_orders | 3 | 2026-11-04T22:44:31Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation and weather data for Amsterdam is not tracked in the database. However, looking at the available order data for customers located in the" |
| frozen | native-governed | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 1 | 2026-11-03T16:59:35Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation data for Amsterdam is not available in the database. However, for orders placed by customers in the Netherlands (`NL`), **3 orders** wer" |
| frozen | native-governed | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 2 | 2026-11-03T20:07:36Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation and weather data for Amsterdam are not available in the database. However, for customers in the Netherlands (`NL`), **3 orders** were pl" |
| frozen | native-governed | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 3 | 2026-11-03T20:26:01Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation and weather data for Amsterdam are not available in the dataset. However, on both **1 October 2026** and **2 October 2026**, customers i" |
| frozen | native-graph | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 1 | 2026-11-03T15:01:19Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather/precipitation data for Amsterdam is not tracked in the available database tables. However, looking at orders placed by customers in the Nether" |
| frozen | native-graph | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 2 | 2026-11-03T15:50:12Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The available dataset contains order and customer data but does not include weather or precipitation data for Amsterdam. For the Netherlands (`NL`), *" |
| frozen | native-graph | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 3 | 2026-11-03T16:10:24Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation and weather data are not tracked in the available database tables; however, order counts for customers in the Netherlands are available " |
| frozen | native-kc | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 1 | 2026-11-03T12:07:50Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation and weather data for Amsterdam are not available in the dataset. However, customers in the Netherlands placed **3 orders** on October 1," |
| frozen | native-kc | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 2 | 2026-11-03T12:56:07Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation and weather data for Amsterdam is not available in the database. However, customers in the Netherlands placed **3 orders** on both **1 O" |
| frozen | native-kc | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 3 | 2026-11-03T13:14:19Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data for Amsterdam is not available in the dataset. However, for the dates requested, customers in the Netherlands placed **" |
| frozen | native-kc-max | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 1 | 2026-11-04T17:48:16Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "The database does not contain weather or precipitation data for Amsterdam. However, on both **1 October 2026** and **2 October 2026**, customers in th" |
| frozen | native-kc-max | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 2 | 2026-11-04T18:08:28Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data are not available in the dataset. However, customers in the Netherlands placed **3 orders** on both **1 October 2026** " |
| frozen | native-kc-max | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 3 | 2026-11-04T18:27:41Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation and weather data are not tracked in the database. However, for orders placed by customers in the Netherlands (`NL`): - On **1 October 20" |
| frozen | native-kc-reach | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 1 | 2026-11-03T20:48:48Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation/weather data for Amsterdam is not tracked in the available database tables. However, on both **1 October 2026** and **2 October 2026**, " |
| frozen | native-kc-reach | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 2 | 2026-11-03T21:06:21Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation data for Amsterdam is not available in the database. However, customers in the Netherlands placed **3 orders** on **1 October 2026** and" |
| frozen | native-kc-reach | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 3 | 2026-11-03T21:52:46Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation data for Amsterdam is not available in the dataset. However, customers in the Netherlands placed **3 orders** on both **1 October 2026**" |
| frozen | native-shaped | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 1 | 2026-11-03T13:58:02Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation and weather data are not tracked in the database. However, on both **1 October 2026** and **2 October 2026**, customers in the Netherlan" |
| frozen | native-shaped | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 2 | 2026-11-03T14:14:10Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Precipitation data for Amsterdam is not available in the database. However, customers in the Netherlands placed **3 orders** on both 1 October 2026 (g" |
| frozen | native-shaped | gda (MODEL_UNSPECIFIED) | bet_wetter_day_nl_orders | 3 | 2026-11-03T14:55:51Z | chance | cannot compare precipitation; states NL orders for both days, right only because both days have 3 orders (fixture tie) | "Weather and precipitation data for Amsterdam is not available in the database. For orders placed by customers in the Netherlands: - On **1 October 202" |
| frozen | native-kc | gda (MODEL_UNSPECIFIED) | calls_about_returns | 3 | 2026-11-03T13:04:17Z | chance | declines (no call data); 3 is the count of product returns | "There is no data or table tracking customer service calls ... 3 product returns recorded" |
| frozen | baseline | claude-haiku-5-5 | customers_to_date | 1 | 2026-11-03T21:17:32Z | chance | main figure 10 (first-order proxy); 30 is the customer table's row count (vacuous as-of cut) | "10 customers had placed their first order by 30 September 2026, out of 30 in total" |
| frozen | baseline | claude-haiku-5-5 | customers_to_date | 2 | 2026-11-03T21:26:32Z | chance | main figure 10 (proxy); 30 is the customer table's row count | "10 customers had placed a first order by 30 September 2026 ... out of 30 in the customer table" |
| frozen | baseline | claude-haiku-5-5 | customers_to_date | 3 | 2026-11-03T21:35:23Z | chance | main figure 10 (proxy); 30 is the customer table's row count | "By 30 September 2026, 10 customers had a first order (out of 30 in the customer table" |
| frozen | baseline | nemotron:free | customers_to_date | 1 | 2026-11-03T03:52:16Z | chance | main figure 10 (proxy); 30 is the customer table's row count | "10 customers had signed up by the end of September 2026 ... out of 30 total customers in the table" |
| frozen | custom-toolbox | claude-haiku-5-5 | engaged_customers_week | 1 | 2026-11-04T17:34:38Z | chance | declines; 9 is a per-day ordering-customer count in a list | "I can't answer this ... the per-day distinct ordering customers were 4, 3, 4, 4, 9 and 9" |
| frozen | custom-toolbox | claude-haiku-5-5 | engaged_customers_week | 3 | 2026-11-04T17:47:06Z | chance | declines; 9 is the top of a per-day range | "I can't answer this ... daily order-customer counts for 27 Sep to 2 Oct (3 to 9 per day)" |
| frozen | custom-toolbox | nemotron:free | engaged_customers_week | 1 | 2026-11-06T01:59:07Z | chance | declines; 9 is a per-day ordering-customer count in a list | "I don't have a metric for general site or CRM activity ... Sep 27: 4, Sep 28: 3, ..." |
| frozen | native-governed | gda (MODEL_UNSPECIFIED) | lead_to_booking_rate | 2 | 2026-11-03T17:05:47Z | chance | gives only per-day rates 33.3% and 25%; 30 is 'within 30 days' from the metric definition | "33.3% of leads created on 1 October 2026 and 25.0% ... went on to book within 30 days" |
| frozen | native-mcp | claude-haiku-5-5 | lead_to_booking_rate | 2 | 2026-11-04T17:54:36Z | chance | declines a combined figure; 30 is 'within 30 days' | "I can't give a single figure for 1–2 October ... Per day, within 30 days of creation" |
| frozen | cc-metricflow | cc (fresh-haiku) | page_views_one_day | 2 | 2026-11-05T00:37:23Z | chance | no page-view count; 5 is the site-session count | "The semantic layer has no page-view count; the closest metric is Site sessions ... 5 sessions" |
| frozen | cc-metricflow | cc (fresh-sonnet) | page_views_one_day | 2 | 2026-11-05T00:48:14Z | chance | no page-view metric; 5 is the site-session count | "The semantic layer has no metric that counts page views; the closest is Site sessions ... 5 sessions" |
| frozen | baseline | claude-haiku-5-5 | view_to_cart_rate | 1 | 2026-11-03T21:19:05Z | chance | main figure 60%; the stored 0.8 is quoted and rejected | "the share is 60%. The table's stored `view_to_cart_rate` shows 0.8 ... but it doesn't match" |
| frozen | baseline | claude-haiku-5-5 | view_to_cart_rate | 2 | 2026-11-03T21:28:09Z | chance | main figure 60%; the stored 0.8 is quoted and rejected | "3 of the 5 site sessions added to cart, so 60% ... stored `view_to_cart_rate` column" |
| frozen | baseline | claude-haiku-5-5 | view_to_cart_rate | 3 | 2026-11-03T21:37:03Z | chance | main figure 60%; the stored 0.8 is quoted and rejected | "a share of 60%. The stored `view_to_cart_rate` column shows 0.8 ... doesn't match" |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | returns_one_day | 3 | 2026-11-04T21:58:20Z | infra | empty answer (no text, no tool call), scored wrong | "(empty answer text)" |
| frozen | baseline | claude-haiku-5-5 | active_customers | 1 | 2026-11-03T21:16:14Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Nine distinct customers bought on 2 October 2026, according to `gold.daily_sales`. That day also had 15 orders, 3 of which were cancelled, and the tab" |
| frozen | custom-hybrid | claude-haiku-5-5 | active_customers | 2 | 2026-11-04T18:37:59Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Nine distinct customers placed a non-cancelled order on 2 October 2026, using the Active customers metric (cancelled orders excluded). The data is lat" |
| frozen | custom-toolbox | claude-haiku-5-5 | active_customers | 2 | 2026-11-04T17:39:17Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Nine distinct customers bought from the shop on 2 October 2026, according to the daily sales metric for that day. That day also had 15 orders, 3 of th" |
| frozen | native-mcp | claude-haiku-5-5 | active_customers | 1 | 2026-11-04T17:32:18Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Nine distinct customers bought from us on 2 October 2026 (UTC order date), counting only orders not cancelled (12 such orders). The business catalog d" |
| frozen | custom-hybrid | nemotron:free | bet_applicants_reaching_interview | 1 | 2026-11-05T00:21:51Z | scorer_miss | whole percent 67% for 66.67% (case expected_sql defective); scored confident-wrong | "About 67% (2 of 3) of the candidates who applied in September 2026 reached the interview stage or beyond (both were hired), covering applications from" |
| frozen | native-mcp | claude-haiku-5-5 | bet_applicants_reaching_interview | 1 | 2026-11-04T17:43:57Z | scorer_miss | whole percent 67% for 66.67% (case expected_sql defective); scored confident-wrong | "About 67% (2 of 3) of candidates who applied in September 2026 reached the interview stage or beyond. The two were K-001 and K-005, both hired; the th" |
| frozen | native-mcp | claude-haiku-5-5 | bet_applicants_reaching_interview | 2 | 2026-11-04T18:03:21Z | scorer_miss | whole percent 67% for 66.67% (case expected_sql defective); scored unclear | "**About 67% (2 of 3)** of the candidates who applied in September 2026 are at the interview stage or beyond, based on their current stage as of the la" |
| frozen | custom-hybrid | claude-haiku-5-5 | bet_customers_over_three_orders | 3 | 2026-11-04T18:52:28Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Ten customers placed more than three orders between 17 August and 2 October 2026. This counts all orders placed, cancelled included, per the Orders me" |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_customers_over_three_orders | 1 | 2026-11-03T20:50:11Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Ten customers placed more than three orders between 17 August and 2 October 2026. Each of the ten placed 18 to 24 orders, counting cancelled orders, s" |
| frozen | custom-hybrid | claude-haiku-5-5 | bet_customers_september | 2 | 2026-11-04T18:41:45Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Ten distinct customers placed a non-cancelled order in September 2026 (1–30 September). I used the "Active customers" metric, which counts distinct cu" |
| frozen | custom-hybrid | claude-haiku-5-5 | bet_customers_september | 3 | 2026-11-04T18:49:58Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Ten distinct customers bought from us in September 2026 (1–30 September), counting customers with at least one non-cancelled order. Freshness:  " |
| frozen | custom-metricflow | claude-haiku-5-5 | bet_customers_september | 1 | 2026-11-03T20:48:15Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Ten distinct customers placed a non-cancelled order in September 2026 (1–30 September), per the "Active customers" metric (customers_distinct). Freshn" |
| frozen | native-context | gda (MODEL_UNSPECIFIED) | bet_p90_order | 2 | 2026-11-03T20:08:33Z | scorer_miss | 158 EUR = 158.125 rounded / nearest-rank; parser needs 0.006; scored confident-wrong | "The 90th percentile order amount for orders placed between 17 August and 2 October 2026 was **158 EUR**." |
| frozen | native-context-bare | gda (LATEST_GA_MODEL) | bet_p90_order | 1 | 2026-11-04T17:54:20Z | scorer_miss | 158 EUR = 158.125 rounded / nearest-rank; parser needs 0.006; scored confident-wrong | "The 90th percentile order amount for orders placed between 17 August and 2 October 2026 was **158 EUR**." |
| frozen | native-context-bare | gda (LATEST_GA_MODEL) | bet_p90_order | 3 | 2026-11-04T18:36:52Z | scorer_miss | 158 EUR = 158.125 rounded / nearest-rank; parser needs 0.006; scored confident-wrong | "The 90th percentile order amount for orders placed between 17 August and 2 October 2026 was **158 EUR**." |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED) | bet_p90_order | 1 | 2026-11-03T20:46:22Z | scorer_miss | 158 EUR = 158.125 rounded / nearest-rank; parser needs 0.006; scored confident-wrong | "The 90th percentile order amount for all orders placed between 17 August and 2 October 2026 was **158 EUR**." |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED) | bet_p90_order | 3 | 2026-11-03T21:52:36Z | scorer_miss | 158 EUR = 158.125 rounded / nearest-rank; parser needs 0.006; scored confident-wrong | "The 90th percentile order amount for all orders placed between 17 August 2026 and 2 October 2026 was **158 EUR**." |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | bet_p90_order | 2 | 2026-11-04T21:46:24Z | scorer_miss | 158 EUR = 158.125 rounded / nearest-rank; parser needs 0.006; scored unclear | "The **90th percentile order amount** for all orders placed between 17 August and 2 October 2026 was **158 EUR** (based on 210 total orders). ### Order" |
| frozen | native-mcp | nemotron:free | bet_p90_order | 1 | 2026-11-06T01:11:36Z | scorer_miss | 158 EUR = 158.125 rounded / nearest-rank; parser needs 0.006; scored confident-wrong | "The 90th percentile order amount was **158 EUR** for all orders placed between **17 August and 2 October 2026**." |
| frozen | custom-metricflow | claude-sonnet-5-5 | bet_top_return_reason_share | 3 | 2026-11-03T22:21:52Z | scorer_miss | expected count written as a word at the headline; scored wrong | "Damaged goods was the largest return reason for returns dated 1–4 October 2026. It accounted for 12.50 EUR of the 24.75 EUR returned, which is about h" |
| frozen | baseline | claude-haiku-5-5 | bookings_wow_growth | 1 | 2026-11-03T21:19:43Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Bookings rose from 11 in the prior week (7–13 September 2026) to 14 in the week of 14–20 September 2026, an increase of 3 bookings or about 27% week o" |
| frozen | baseline | claude-haiku-5-5 | bookings_wow_growth | 2 | 2026-11-03T21:28:46Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Bookings rose from 11 in the week of 7–13 September 2026 to 14 in the week of 14–20 September 2026, an increase of 3 bookings or about 27% week over w" |
| frozen | baseline | claude-haiku-5-5 | bookings_wow_growth | 3 | 2026-11-03T21:37:40Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored wrong | "Bookings in the week of 14 to 20 September 2026 were 14, up 3 (about 27%) from 11 in the prior week of 7 to 13 September. Both `gold.marketing_daily` " |
| frozen | custom-toolbox | claude-haiku-5-5 | bookings_wow_growth | 1 | 2026-11-04T17:35:07Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Bookings rose from 11 in the week of 7–13 September 2026 to 14 in the week of 14–20 September 2026, an increase of 3 bookings or about 27%. The prior " |
| frozen | custom-toolbox | claude-haiku-5-5 | bookings_wow_growth | 2 | 2026-11-04T17:41:27Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Bookings rose from 11 in the week of 7–13 September 2026 to 14 in the week of 14–20 September 2026, an increase of 3 bookings, or about 27%. The prior" |
| frozen | custom-toolbox | claude-haiku-5-5 | bookings_wow_growth | 3 | 2026-11-04T17:47:37Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Bookings rose from 11 in the week of 7–13 September 2026 to 14 in the week of 14–20 September, an increase of 3 bookings or about 27%. This treats the" |
| frozen | custom-toolbox | claude-sonnet-5-5 | bookings_wow_growth | 2 | 2026-11-04T18:14:53Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Bookings rose from 11 in the week of 7–13 September 2026 to 14 in the week of 14–20 September 2026. That is an increase of 3 bookings, or about 27%. T" |
| frozen | custom-toolbox | claude-sonnet-5-5 | bookings_wow_growth | 3 | 2026-11-04T18:22:14Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Bookings grew by 3, from 11 to 14, which is about 27% more. The comparison is the week of 14–20 September 2026 against 7–13 September 2026. - **14–20 " |
| frozen | custom-hybrid | claude-haiku-5-5 | calls_about_returns | 1 | 2026-11-04T18:31:45Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Three customer calls on 1 and 2 October 2026 were labelled with the returns topic. This is a model-derived count (calls labelled by gemini-3.5-flash u" |
| frozen | custom-hybrid | claude-haiku-5-5 | calls_about_returns | 2 | 2026-11-04T18:40:21Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Three calls on 1 and 2 October 2026 were labelled as about returns, out of 13 labelled calls that period. The count comes from the model-derived "Call" |
| frozen | custom-hybrid | claude-haiku-5-5 | calls_about_returns | 3 | 2026-11-04T18:48:38Z | scorer_miss | expected count written as a word at the headline; scored unclear | "Three of the customer calls on 1 and 2 October 2026 were about returns (topic labelled returns), out of 9 calls labelled that period. These topic labe" |
| frozen | custom-metricflow | claude-haiku-5-5 | calls_about_returns | 1 | 2026-11-03T20:46:59Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Three customer calls on 1 and 2 October 2026 were labelled with the topic "returns", out of 9 calls labelled in that period. These counts are model-de" |
| frozen | custom-metricflow | claude-haiku-5-5 | calls_about_returns | 3 | 2026-11-03T21:00:51Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Three of the customer calls on 1 and 2 October 2026 were about returns, out of 12 calls labelled in that period. These counts come from a model-derive" |
| frozen | custom-metricflow | claude-sonnet-5-5 | calls_about_returns | 1 | 2026-11-03T21:47:33Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Three calls on 1 and 2 October 2026 were labelled as being about returns. The topic comes from a model label (gemini-3.5-flash, prompt v1), so it is a" |
| frozen | custom-metricflow | claude-sonnet-5-5 | calls_about_returns | 2 | 2026-11-03T21:56:42Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Three calls on 1 and 2 October 2026 were about returns. This count comes from topic labels that a language model (gemini-3.5-flash, prompt v1) assigne" |
| frozen | native-mcp | claude-haiku-5-5 | calls_about_returns | 3 | 2026-11-04T18:16:03Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Three customer calls were about returns on 1 and 2 October 2026: two on 1 October and one on 2 October. This counts calls labelled with the topic "ret" |
| frozen | custom-toolbox | claude-sonnet-5-5 | damaged_return_share | 1 | 2026-11-04T18:06:27Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Half of the returns were damaged: 3 of 6 returns, between 1 August and 31 October 2026. By value the damaged share is about 69.6% (€62.50 of €89.75). " |
| frozen | baseline | claude-haiku-5-5 | objection_rate | 2 | 2026-11-03T21:28:34Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "In 1 and 2 October 2026, 4 of 12 labelled customer calls (33%) included a customer objection. The topic-level rows sum to these totals, but if a singl" |
| frozen | baseline | claude-haiku-5-5 | objection_rate | 3 | 2026-11-03T21:37:27Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 33% (4 of 12 labelled calls) on 1 and 2 October 2026 involved a customer objection. This sums the per-topic rows in `gold.call_signals_daily`, s" |
| frozen | custom-metricflow | claude-haiku-5-5 | objection_rate | 3 | 2026-11-03T21:00:55Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 33% of labelled customer calls on 1 and 2 October 2026 had an objection from the customer: 4 of 12 calls. This is the model-derived objection ra" |
| frozen | native-mcp | claude-haiku-5-5 | objection_rate | 3 | 2026-11-04T18:16:12Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored wrong | "About 33% of our labelled customer calls on 1–2 October 2026 had a customer objection: 4 of 12 calls (objection rate, a ratio of totals over the two d" |
| frozen | custom-hybrid | claude-haiku-5-5 | orders_over_100 | 1 | 2026-11-04T18:29:56Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Six orders over 100 EUR were placed on 1 and 2 October 2026: 3 on 1 October and 3 on 2 October. The count includes cancelled orders, since the Orders " |
| frozen | native-mcp | claude-haiku-5-5 | orders_over_100 | 2 | 2026-11-04T17:51:45Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Six orders over 100 EUR were placed on 1 and 2 October 2026 (by UTC order date), all with status "shipped". The orders table holds 30 orders over thos" |
| frozen | baseline | claude-haiku-5-5 | outreach_reply_rate | 1 | 2026-11-03T21:19:11Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 67% of the outreach messages sent from 1 to 3 October 2026 got a reply: 4 of 6 messages (messages_replied / messages_sent, summed over the three" |
| frozen | baseline | claude-haiku-5-5 | outreach_reply_rate | 2 | 2026-11-03T21:28:14Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 67% of the outreach messages sent from 1 to 3 October 2026 got a reply: 4 of 6 messages (messages_replied / messages_sent, summed over those thr" |
| frozen | baseline | claude-haiku-5-5 | outreach_reply_rate | 3 | 2026-11-03T21:37:09Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 67% of the outreach messages sent from 1 to 3 October 2026 got a reply: 4 of 6 messages (messages_replied / messages_sent in gold.partner_outrea" |
| frozen | native-mcp | claude-haiku-5-5 | outreach_reply_rate | 3 | 2026-11-04T18:15:28Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 67% of the outreach messages sent from 1 to 3 October 2026 got a reply: 4 of 6 messages (UTC sent dates). This is a snapshot as of the latest da" |
| frozen | baseline | claude-haiku-5-5 | partners_engaged_one_day | 3 | 2026-11-03T21:37:13Z | scorer_miss | expected count written as a word at the headline; scored wrong | "Two partners were engaged in partner outreach on 2 October 2026, per the `partners_engaged` column in `gold.partner_outreach_daily`. That day, 1 messa" |
| frozen | cc-metricflow | cc (fresh-haiku) | partners_engaged_one_day | 3 | 2026-11-05T01:04:13Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Two partners replied to our outreach on 2 October 2026 (partners engaged, a count of distinct partners, for that one day). Late: partner_outreach.silv" |
| frozen | custom-hybrid | claude-haiku-5-5 | signup_to_first_order_rate | 2 | 2026-11-04T18:38:49Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 33% (1 in 3) of the 9 customers who signed up in September 2026 placed an order within 30 days of signing up, for signups dated 1–30 September 2" |
| frozen | native-mcp | claude-haiku-5-5 | signup_to_first_order_rate | 2 | 2026-11-04T17:52:30Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 33% of the 9 customers who signed up in September 2026 placed an order within 30 days of signing up (3 of 9). I counted an order as any order pl" |
| frozen | custom-hybrid | claude-haiku-5-5 | signups_september | 1 | 2026-11-04T18:30:08Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Nine new customers signed up in September 2026 (1–30 September), counted on the day they signed up.  " |
| frozen | custom-hybrid | claude-haiku-5-5 | signups_september | 2 | 2026-11-04T18:38:40Z | scorer_miss | expected count written as a word at the headline; scored unclear | "Nine new customers signed up in September 2026 (1–30 September), based on the Signups metric, which counts customers on the day they signed up. Freshn" |
| frozen | custom-hybrid | claude-haiku-5-5 | signups_september | 3 | 2026-11-04T18:46:55Z | scorer_miss | expected count written as a word at the headline; scored unclear | "Nine new customers signed up in September 2026 (1–30 September), based on the Signups metric, which counts customers on the day they signed up. Freshn" |
| frozen | native-mcp | claude-haiku-5-5 | signups_september | 1 | 2026-11-04T17:34:24Z | scorer_miss | expected count written as a word at the headline; scored confident-wrong | "Nine new customers signed up in September 2026 (1–30 Sep, UTC days), per the governed `customers_daily` table's signups metric. Signups are recorded o" |
| frozen | native-mcp | claude-haiku-5-5 | signups_september | 3 | 2026-11-04T18:11:37Z | scorer_miss | expected count written as a word at the headline; scored unclear | "Nine new customers signed up in September 2026 (1–30 September, by UTC signup date), based on the business's "Signups" definition: a count of customer" |
| hard | baseline | claude-haiku-5-5 | hard_customer_base_turkey | 2 | 2026-11-03T22:58:25Z | chance | declines a reliable figure; 5 is the all-time TR record count (the as-of date never bites) | "I can't give a reliable end-of-September 2026 figure ... lists 5 Turkish (TR) customer records" |
| hard | baseline | claude-haiku-5-5 | hard_customer_base_turkey | 3 | 2026-11-03T23:03:42Z | chance | main figure 2 (first-order proxy); 5 is the TR table total | "we had 2 Turkish customers whose first order was on or before 30 September ... only 5 Turkish customers in total" |
| hard | cc-metricflow | cc (fresh-haiku) | hard_august_signups_bought | 1 | 2026-11-04T20:02:16Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored wrong | "Of the 11 customers who signed up in August 2026, 4 (36 %) had placed a non-cancelled order by 10 October 2026, computed as Active customers (distinct" |
| hard | cc-metricflow | cc (fresh-haiku) | hard_august_signups_bought | 3 | 2026-11-05T00:08:26Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 36% (4 of the 11 customers who signed up in August 2026) had placed a non-cancelled order by 10 October 2026, counting orders from 1 August to 1" |
| hard | custom-hybrid | claude-haiku-5-5 | hard_august_signups_bought | 3 | 2026-11-04T19:07:37Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Of the 11 customers who signed up in August 2026, 4 had placed a non-cancelled order by 10 October 2026, a share of about 36% (4 of 11). The cohort co" |
| hard | custom-metricflow | claude-haiku-5-5 | hard_august_signups_bought | 1 | 2026-11-03T22:41:55Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Of the 11 customers who signed up in August 2026, 4 had placed a non-cancelled order by 10 October 2026, a share of 36% (4 of 11). The order data cove" |
| hard | custom-metricflow | claude-haiku-5-5 | hard_august_signups_bought | 2 | 2026-11-03T22:45:46Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Of the 11 customers who signed up in August 2026, 4 had bought by 10 October 2026, a share of about 36% (4 of 11). The 4 counts distinct customers wit" |
| hard | custom-metricflow | claude-haiku-5-5 | hard_august_signups_bought | 3 | 2026-11-03T22:49:34Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Of the 11 customers who signed up in August 2026, 4 had placed a non-cancelled order by 10 October 2026, a share of about 36% (4 of 11). These figures" |
| hard | custom-metricflow | nemotron:free | hard_august_signups_bought | 2 | 2026-11-04T00:58:50Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "4 of the 11 customers who signed up in August 2026 had placed a non‑cancelled order by 10 October 2026 – a share of about 36 %. Freshness:  " |
| hard | native-mcp | claude-haiku-5-5 | hard_august_signups_bought | 2 | 2026-11-04T18:45:26Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "**36% (4 of 11 customers)** who signed up in August 2026 had placed at least one order by 10 October 2026. This counts all orders, including cancelled" |
| hard | custom-metricflow | claude-haiku-5-5 | hard_budget_pacing | 1 | 2026-11-03T22:41:24Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored wrong | "By the end of September 2026, the remaining budget was 4,130 EUR and ad spend for the month was 6,270 EUR. The semantic layer has no total-budget metr" |
| hard | baseline | claude-haiku-5-5 | hard_candidates_still_in_running | 1 | 2026-11-03T22:56:07Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored unclear | "About 33% (2 of 6): the 6 applications received 25 Sep to 2 Oct 2026 are the cohort, and at the end of 4 October 2 candidates were still in interview " |
| hard | baseline | claude-haiku-5-5 | hard_candidates_still_in_running | 2 | 2026-11-03T23:01:11Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored wrong | "The tables can't answer this exactly. The applications table gives 6 applications from 25 September to 2 October, but the stage table has no applicati" |
| hard | baseline | claude-haiku-5-5 | hard_candidates_still_in_running | 3 | 2026-11-03T23:06:32Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored unclear | "About 33% (2 of 6) based on the 4 October stage snapshot, but this is a rough estimate. The six applications from 25 September to 2 October come from " |
| hard | cc-metricflow | cc (fresh-haiku) | hard_candidates_still_in_running | 2 | 2026-11-04T23:55:00Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "33% (2 of the 6 people who applied between 25 September and 2 October 2026, a share of applicants) were still in the running at the end of 4 October, " |
| hard | cc-metricflow | cc (fresh-haiku) | hard_candidates_still_in_running | 3 | 2026-11-05T00:08:26Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 33% (2 of the 6 candidates who applied from 25 September to 2 October 2026) were still in the running at the end of 4 October 2026, counting the" |
| hard | custom-hybrid | claude-haiku-5-5 | hard_candidates_still_in_running | 1 | 2026-11-04T18:58:40Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Of the 6 people who applied between 25 September and 2 October 2026, 2 were still in the running at the end of 4 October, a share of about 33% (1 in i" |
| hard | custom-hybrid | claude-haiku-5-5 | hard_candidates_still_in_running | 2 | 2026-11-04T19:03:21Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Of the 6 candidates who applied between 25 September and 2 October 2026, 2 were still in the running at the end of 4 October, a share of about 33% (2 " |
| hard | custom-hybrid | claude-haiku-5-5 | hard_candidates_still_in_running | 3 | 2026-11-04T19:07:57Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Of the 6 people who applied between 25 September and 2 October 2026, 2 were still in the running at the end of 4 October, a share of 33% (2 of 6). Tho" |
| hard | custom-metricflow | claude-haiku-5-5 | hard_candidates_still_in_running | 1 | 2026-11-03T22:42:10Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About one third (33%, 2 of 6) of the candidates who applied between 25 September and 2 October 2026 were still in the running at the end of 4 October " |
| hard | custom-metricflow | claude-haiku-5-5 | hard_candidates_still_in_running | 2 | 2026-11-03T22:46:01Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored unclear | "**About a third (2 of 6, 33%) of the candidates who applied between 25 September and 2 October 2026 were still in the running at the end of 4 October." |
| hard | custom-metricflow | claude-haiku-5-5 | hard_candidates_still_in_running | 3 | 2026-11-03T22:49:49Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Of the 6 people who applied between 25 September and 2 October 2026, 2 were still in the running at the end of 4 October, a share of 33% (2 of 6). The" |
| hard | custom-metricflow | nemotron:free | hard_candidates_still_in_running | 2 | 2026-11-04T00:59:39Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "2 of the 6 people who applied between 25 September and 2 October 2026 (about 33%) were still in the running — at stage screen or interview — at the en" |
| hard | native-mcp | claude-haiku-5-5 | hard_candidates_still_in_running | 1 | 2026-11-04T18:36:20Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "Two of the six candidates who applied between 25 September and 2 October 2026 were still in the running at the end of 4 October, so the share is **33%" |
| hard | native-mcp | claude-haiku-5-5 | hard_candidates_still_in_running | 2 | 2026-11-04T18:46:13Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "About 33% (2 of 6 applicants) were still in the running at the end of 4 October 2026. The six people who applied between 25 September and 2 October we" |
| hard | baseline | claude-haiku-5-5 | hard_repeat_rate_october | 1 | 2026-11-03T22:54:39Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored wrong | "Roughly 59% (10 of 17 customers) of those who bought between 1 and 10 October 2026 had more than one order. This is a proxy: `gold.customer_lifetime` " |
| hard | baseline | claude-haiku-5-5 | hard_repeat_rate_october | 2 | 2026-11-03T22:59:44Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored wrong | "I can't get an exact figure from these tables. The closest proxy is about 59% (10 of 17 customers who bought 1–10 October 2026 have more than one life" |
| hard | cc-metricflow | cc (fresh-haiku) | hard_repeat_rate_october | 3 | 2026-11-05T00:08:26Z | scorer_miss | states the share as a fraction ("the share is 10 of 17"); the parser reads only single numbers; scored confident-wrong | "From 1 to 10 October 2026, 10 of the 17 active customers (customers with a non-cancelled order in that period) were repeat customers, meaning they hav" |
| hard | custom-metricflow | claude-haiku-5-5 | hard_repeat_rate_october | 1 | 2026-11-03T22:41:00Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "From 1 to 10 October 2026, 10 of the 17 customers who bought (non-cancelled orders) had placed two or more orders in all, a repeat purchase share of a" |
| hard | custom-metricflow | claude-haiku-5-5 | hard_repeat_rate_october | 3 | 2026-11-03T22:48:38Z | scorer_miss | whole-number rounding of expected (e.g. 33% for 33.33%); scored confident-wrong | "From 1 to 10 October 2026, 10 of the 17 active customers (customers with a non-cancelled order in that window) had two or more orders, a repeat purcha" |
| hard | custom-metricflow | nemotron:free | hard_repeat_rate_october | 1 | 2026-11-04T00:44:47Z | scorer_miss | states the share as a fraction ("the share is 10 of 17"); the parser reads only single numbers; scored confident-wrong | "The semantic layer has no single “repeat purchase rate” metric; the closest metrics are active customers and repeat customers. For 1–10 October 2026 t" |
| hard | native-mcp | claude-haiku-5-5 | hard_replies_within_12_hours | 2 | 2026-11-04T18:45:43Z | scorer_miss | expected count written as a word at the headline; scored unclear | "Half of the 6 partner outreach messages sent 1–3 October 2026 (3 of 6) got a reply within 12 hours of being sent. The figure is based on the first rep" |

## What the redactions change

Dropping the 208 runs (the overlay: each run key leaves the score; `case_shares`-style means over cases of each case's finished runs) moves accuracy by at most 6.1 points and confident-wrong by at most 5.2 points, and only for arms with a chance carry or a scorer miss.
"chance+infra" drops only the 122 runs a rerun can fix; "all" also drops the 86 scorer-miss runs.
hard-v2 moves exactly as hard v1 for these arms (the redacted runs are carried v1 runs; no new-case run is redacted).

Direction by arm:
- Chance carries inflate whoever declines with a number beside the decline: baseline haiku frozen loses 3.8 points (61.1% → 57.3%), custom-metricflow opus 1.3, custom-toolbox haiku 1.3; the data agents lose 0.1 to 1.0 (mostly the wetter-day case).
- Scorer misses deflate the prose-writing Haiku arms: custom-metricflow haiku hard +6.1 points (73.6% → 79.7%) and confident-wrong 9.3% → 4.1%; custom-hybrid haiku +3.5 frozen and +2.7 hard, confident-wrong to 0.0% on both; native-mcp haiku +2.8 frozen and +3.1 hard.
- Rescoring the scorer misses as right, which a parser fix would do, moves the same arms further than dropping them: custom-metricflow haiku hard 73.6% → 80.6%, custom-hybrid haiku frozen 80.9% → 85.1%, native-mcp haiku frozen 90.3% → 93.8%, baseline haiku hard 56.6% → 60.5%, cc-metricflow fresh-haiku hard 54.3% → 58.1%.
- The top of each set does not move: frozen native-mcp sonnet 95.8% (unchanged) and native-context-bare THINKING 94.1% → 94.7%; hard native-context-bare THINKING and FAST 94.6% (unchanged).
  Below the top, native-mcp haiku frozen rises from 90.3% to 93.1%, past native-kc-max (91.7% → 91.6%), and on the hard set custom-metricflow haiku and custom-hybrid haiku rise 6.1 and 2.7 points.
  I did not rerun the paired bootstrap; the report's `step_two` should be rerun on the overlay before any verdict is read.

### Per arm and model

Mean over cases of the share of each case's finished runs (k ≤ 3), as `case_shares` computes it; "chance+infra" drops only those runs, "all" also drops the scorer-miss runs. Only arms whose numbers move are listed.

**frozen**

| arm | model | runs before → after | accuracy now | after chance+infra | after all | conf.-wrong now | after chance+infra | after all |
|---|---|---|---:|---:|---:|---:|---:|---:|
| baseline | claude-haiku-5-5 | 288 → 260 | 61.1% | 57.3% | 60.1% | 6.6% | 7.5% | 4.8% |
| baseline | nemotron:free | 56 → 54 | 67.9% | 66.7% | 66.7% | 10.7% | 11.1% | 11.1% |
| cc-metricflow | cc (fresh-haiku) | 288 → 279 | 72.6% | 71.6% | 72.0% | 4.5% | 4.6% | 4.3% |
| cc-metricflow | cc (fresh-opus) | 50 → 49 | 74.0% | 73.5% | 73.5% | 0.0% | 0.0% | 0.0% |
| cc-metricflow | cc (fresh-sonnet) | 288 → 281 | 72.9% | 72.3% | 72.3% | 2.1% | 2.1% | 2.1% |
| cc-metricflow | cc (haiku) | 96 → 95 | 66.7% | 66.3% | 66.3% | 5.2% | 5.3% | 5.3% |
| cc-metricflow | cc (opus) | 96 → 95 | 70.8% | 70.5% | 70.5% | 4.2% | 4.2% | 4.2% |
| cc-metricflow | cc (sonnet) | 96 → 95 | 70.8% | 70.5% | 70.5% | 1.0% | 1.1% | 1.1% |
| cc-metricflow | cc (subject-haiku) | 96 → 95 | 69.8% | 69.5% | 69.5% | 4.2% | 4.2% | 4.2% |
| custom-hybrid | claude-haiku-5-5 | 288 → 271 | 80.9% | 80.6% | 84.4% | 3.1% | 3.1% | 0.0% |
| custom-hybrid | nemotron:free | 96 → 93 | 85.4% | 85.1% | 86.0% | 1.0% | 1.1% | 0.0% |
| custom-metricflow | claude-haiku-5-5 | 288 → 274 | 81.2% | 80.6% | 82.4% | 2.4% | 2.5% | 0.7% |
| custom-metricflow | claude-opus-5-5 | 288 → 280 | 74.7% | 73.4% | 73.4% | 1.7% | 1.8% | 1.8% |
| custom-metricflow | claude-sonnet-5-5 | 288 → 281 | 74.7% | 74.0% | 74.7% | 1.4% | 1.4% | 0.7% |
| custom-metricflow | nemotron:free | 110 → 109 | 81.2% | 81.1% | 81.1% | 0.0% | 0.0% | 0.0% |
| custom-toolbox | claude-haiku-5-5 | 288 → 279 | 43.1% | 41.8% | 42.6% | 3.1% | 3.2% | 1.8% |
| custom-toolbox | claude-sonnet-5-5 | 288 → 282 | 41.7% | 41.1% | 42.1% | 2.4% | 2.5% | 1.4% |
| custom-toolbox | nemotron:free | 96 → 95 | 38.5% | 37.9% | 37.9% | 4.2% | 4.2% | 4.2% |
| native-bare | gda (MODEL_UNSPECIFIED) | 287 → 284 | 80.6% | 80.4% | 80.4% | 15.3% | 15.4% | 15.4% |
| native-context-bare | gda (LATEST_GA_MODEL) | 288 → 283 | 90.3% | 90.2% | 90.2% | 5.2% | 5.3% | 5.3% |
| native-context-bare | gda (MODEL_UNSPECIFIED) | 288 → 283 | 89.6% | 89.5% | 89.5% | 4.5% | 4.6% | 4.6% |
| native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | 288 → 285 | 90.3% | 90.2% | 90.2% | 4.5% | 4.6% | 4.6% |
| native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | 288 → 283 | 94.1% | 94.4% | 94.7% | 1.0% | 1.1% | 1.1% |
| native-context | gda (MODEL_UNSPECIFIED) | 288 → 284 | 87.2% | 87.0% | 87.0% | 5.6% | 5.6% | 5.4% |
| native-governed | gda (MODEL_UNSPECIFIED) | 288 → 283 | 72.9% | 71.9% | 71.9% | 1.0% | 1.1% | 1.1% |
| native-graph | gda (MODEL_UNSPECIFIED) | 288 → 284 | 61.8% | 61.1% | 61.1% | 6.9% | 7.0% | 7.0% |
| native-kc-max | gda (MODEL_UNSPECIFIED) | 288 → 285 | 91.7% | 91.6% | 91.6% | 4.9% | 4.9% | 4.9% |
| native-kc-reach | gda (MODEL_UNSPECIFIED) | 288 → 285 | 86.8% | 86.7% | 86.7% | 6.9% | 7.0% | 7.0% |
| native-kc | gda (MODEL_UNSPECIFIED) | 288 → 284 | 64.2% | 63.5% | 63.5% | 4.2% | 4.2% | 4.2% |
| native-mcp | claude-haiku-5-5 | 288 → 277 | 90.3% | 90.3% | 93.1% | 3.1% | 3.1% | 0.7% |
| native-mcp | nemotron:free | 96 → 95 | 88.5% | 88.5% | 89.5% | 6.2% | 6.2% | 5.3% |
| native-shaped | gda (MODEL_UNSPECIFIED) | 288 → 285 | 61.8% | 61.4% | 61.4% | 5.2% | 5.3% | 5.3% |

**hard**

| arm | model | runs before → after | accuracy now | after chance+infra | after all | conf.-wrong now | after chance+infra | after all |
|---|---|---|---:|---:|---:|---:|---:|---:|
| baseline | claude-haiku-5-5 | 129 → 122 | 56.6% | 55.0% | 56.3% | 7.8% | 9.3% | 9.5% |
| cc-metricflow | cc (fresh-haiku) | 129 → 124 | 54.3% | 54.3% | 54.3% | 7.0% | 7.0% | 5.4% |
| custom-hybrid | claude-haiku-5-5 | 129 → 125 | 81.4% | 81.4% | 84.1% | 3.1% | 3.1% | 0.0% |
| custom-metricflow | claude-haiku-5-5 | 129 → 120 | 73.6% | 73.6% | 79.7% | 9.3% | 9.3% | 4.1% |
| custom-metricflow | nemotron:free | 129 → 126 | 73.6% | 73.6% | 75.2% | 7.0% | 7.0% | 5.0% |
| native-mcp | claude-haiku-5-5 | 129 → 125 | 81.4% | 81.4% | 84.5% | 6.2% | 6.2% | 3.9% |

**hard-v2**

| arm | model | runs before → after | accuracy now | after chance+infra | after all | conf.-wrong now | after chance+infra | after all |
|---|---|---|---:|---:|---:|---:|---:|---:|
| baseline | claude-haiku-5-5 | 129 → 122 | 56.6% | 55.0% | 56.3% | 7.8% | 9.3% | 9.5% |
| cc-metricflow | cc (fresh-haiku) | 129 → 124 | 54.3% | 54.3% | 54.3% | 7.0% | 7.0% | 5.4% |
| custom-hybrid | claude-haiku-5-5 | 129 → 125 | 81.4% | 81.4% | 84.1% | 3.1% | 3.1% | 0.0% |
| custom-metricflow | claude-haiku-5-5 | 129 → 120 | 73.6% | 73.6% | 79.7% | 9.3% | 9.3% | 4.1% |
| custom-metricflow | nemotron:free | 129 → 126 | 73.6% | 73.6% | 75.2% | 7.0% | 7.0% | 5.0% |
| native-mcp | claude-haiku-5-5 | 129 → 125 | 81.4% | 81.4% | 84.5% | 6.2% | 6.2% | 3.9% |

## Recommendation per scorer risk the audits raised

Evidence = runs that actually misled (chance carries / scorer misses) across all arms.

| case or risk | audit | runs that misled | recommendation |
|---|---|---|---|
| `bet_wetter_day_nl_orders` | fixture, scorer | 63 chance | retire (the tie makes every per-day answer right) |
| `bet_median_days_to_hire` | fixture, readings | 15 chance | retire (median of two = governed mean) |
| `bet_peak_checkout_hour` | scorer | 7 chance | retire |
| `customers_to_date` | doubt, scorer/fixture | 4 chance | retire (vacuous as-of; 30 = table size) |
| `bet_median_days_to_interview` | fixture, scorer, expected_sql | 3 chance | retire |
| `bet_median_days_lead_to_booking` | fixture, scorer | 3 chance | retire |
| `engaged_customers_week` | scorer | 3 chance | retire |
| `ambiguous_customers` | scorer, fixture | 3 chance (dates) | retire; if kept, fix date stripping (below) |
| `bet_customers_september` | fixture, scorer | 2 chance, 3 scorer misses | retire |
| `bet_customers_over_three_orders` | fixture, scorer | 2 chance, 2 scorer misses | retire |
| `bet_most_email_opens` | fixture, scorer, label | 2 chance | retire |
| `lead_to_booking_rate` | scorer ("30 days") | 2 chance | retire |
| `page_views_one_day` | scorer | 2 chance | retire |
| `hard_customer_base_turkey` | scorer | 2 chance | retire |
| `calls_about_returns` | scorer | 1 chance, 8 scorer misses | retire; the misses go with the number-word fix |
| `bet_p75_reply_hours` | readings, scorer | 1 chance (date) | retire (readings defect); date fix covers the carry |
| `active_customers`, `signups_september`, `orders_over_100`, `partners_engaged_one_day` | scorer (small counts) | 0 chance; 4, 5, 2, 2 scorer misses (number words) | keep; fix the scorer for every arm (number words) |
| `cancelled_total`, `returns_one_day`, `outreach_messages_sent`, `orders_one_day`, `candidates_in_interview_as_of`, `monthly_active_customers`, `amsterdam_temperature`, `bet_cart_to_checkout_minutes`, `bet_median_days_to_return`, `bet_delivery_calls_per_100_shipped` | scorer (small/common numbers) | 0 | keep: no run misled (fixture defects of `amsterdam_temperature` and `bet_delivery_calls_per_100_shipped` stand on their own audit verdicts) |
| `followup_switch_metric` (15) | note | 0 | keep |
| `bet_peak_page_view_hour`, `bet_istanbul_warmer`, `bet_weekday_most_orders`, `hard_happiest_call_topic` | fixture | 0 chance (answers state the tie or the constant correctly) | retire on the fixture verdict, not on scoring |
| `bet_p90_order` | doubt, readings | 7 scorer misses ("158 EUR") | keep; fix the scorer (whole-number rounding) or accept 158.00 as the nearest-rank reading |
| whole-percent misses: `bookings_wow_growth`, `objection_rate`, `outreach_reply_rate`, `signup_to_first_order_rate`, `hard_candidates_still_in_running`, `hard_august_signups_bought`, `hard_repeat_rate_october`, `hard_budget_pacing`, `bet_applicants_reaching_interview` | scorer (cross-cutting note) | 8, 4, 4, 2, 14, 8, 6, 1, 3 scorer misses | keep; fix the scorer for every arm (whole-percent rounding) |
| `hard_ad_spend_wow` "6%", `time_to_hire` "6 days", `hard_roas_september` "2,056%", `hv2_search_budget_left_drop` "−2,175" | scorer (parser) | 0 | keep; no run misled (the rounding fix covers them anyway) |
| `hard_mqls_social_september` 40, `hard_top_channel_bookings` 31, `hard_runner_up_channel_leads` 20, `hv2_signups_never_ordered` 16, `hard_orders_last_fiscal_quarter` 217, `hard_cost_per_booking_rise` 27 | scorer (small/common, dates, row count) | 0 | keep: no run misled (`hard_orders_last_fiscal_quarter` still has its fixture problem: the fiscal boundary never bites) |
| `hard_active_customers_week` WAU/MAU collision | doubt | 0 | keep |
| absolute 0.006 tolerance on fractions (`return_rate_september`, `hard_refund_rate_by_value`, `hard_followup_cancelling_country`, `hv2_revenue_share_unreturned_orders`, `hv2_top_three_customers_share`) | scorer notes | 0 | keep; optionally make the fraction tolerance relative |
| `ASKS_WHICH` loose (all ambiguous turns) | scorer | 0 | keep the cases; tighten `ASKS_WHICH` anyway before a later version (no run used it) |
| `define` verbatim quote (`followup_how_computed`, `followup_rate_how_computed`) | scorer | 37 define turns wrong despite a correct definition | retire the define turns (or send every define turn to the blind judge), for every arm |

Scorer fixes, each applied to every arm on read (`recode` already rescores logs; `rescore` for the local log):
1. Number words: map `one`…`twenty`, `thirty`, `forty`, `half`, `a third`, `one third`, `two-thirds`, `a quarter`, `three quarters` to values before `_stated` parses (`active_customers`, `signups_september`, `calls_about_returns`, …: 29 misses).
2. Whole-number rounding: accept an integer `n` with `round(e) == n` when the expected value is not itself a small integer and the answer marks it as approximate or as a percentage (`about 33%`, `27%`, `158 EUR`: 55 misses); keep the 0.006 rule for small whole counts so chance carries do not grow.
3. Dates and times: also strip `Sept 30`/`Sep 21–27`, `1–30 Sep`, ISO dates with any dash (U+2011, U+2013), `HH:MM`, `THH:MMZ`, and the cc-metricflow freshness statements, before parsing (5 chance carries).
4. Decline wording: let `DECLINE` match `no [\w-]+(?: [\w-]+){0,4} metric`, so "has no median order value metric" is a decline and its turn is wrong, not confident-wrong (78 turns, mostly cc-metricflow and custom-metricflow).
5. Fractions: read "N of M" stated as the share ("the share is 10 of 17") as N/M (2 misses).

## Limits

- Right turns whose first own figure is an expected number and that carry no decline or competing figure (7,032) were not read one by one; I read the read list (1,638) and spot-checked every small-number case.
- The 78 decline-wording confident-wrong turns were sampled (10 read), not all read.
- The define-turn count (37) comes from reading the 39 turns my paraphrase regex found; a define turn paraphrased in other words could be missed.
- Accuracy deltas use per-case shares over finished runs, not the report's complete-round rule; after redaction most arms have incomplete rounds until reruns land.

## Appendix: per arm and model detail

### Check 2 per arm and model (right turns; carried hard-v2 rows counted under hard)

| set | arm | model | right turns | flagged and read | chance (confirmed) | unclear |
|---|---|---|---:|---:|---:|---:|
| frozen | baseline | claude-haiku-5-5 | 191 | 60 | 18 | 11 |
| frozen | baseline | nemotron:free | 43 | 4 | 1 | 0 |
| frozen | cc-metricflow | cc (fresh-haiku) | 216 | 23 | 8 | 0 |
| frozen | cc-metricflow | cc (fresh-opus) | 39 | 4 | 1 | 0 |
| frozen | cc-metricflow | cc (fresh-sonnet) | 217 | 22 | 7 | 0 |
| frozen | cc-metricflow | cc (haiku) | 66 | 3 | 1 | 0 |
| frozen | cc-metricflow | cc (opus) | 70 | 4 | 1 | 0 |
| frozen | cc-metricflow | cc (sonnet) | 70 | 3 | 1 | 0 |
| frozen | cc-metricflow | cc (subject-haiku) | 69 | 7 | 1 | 0 |
| frozen | custom-hybrid | claude-haiku-5-5 | 239 | 67 | 3 | 0 |
| frozen | custom-hybrid | nemotron:free | 84 | 12 | 2 | 0 |
| frozen | custom-lightdash | nemotron:free | 24 | 1 | 0 | 0 |
| frozen | custom-metricflow | claude-haiku-5-5 | 241 | 46 | 9 | 0 |
| frozen | custom-metricflow | claude-opus-5-5 | 221 | 36 | 8 | 0 |
| frozen | custom-metricflow | claude-sonnet-5-5 | 221 | 27 | 4 | 0 |
| frozen | custom-metricflow | nemotron:free | 94 | 11 | 1 | 0 |
| frozen | custom-toolbox | claude-haiku-5-5 | 142 | 38 | 5 | 9 |
| frozen | custom-toolbox | claude-sonnet-5-5 | 138 | 47 | 3 | 12 |
| frozen | custom-toolbox | nemotron:free | 43 | 7 | 1 | 1 |
| frozen | native-bare | gda (MODEL_UNSPECIFIED) | 240 | 57 | 3 | 7 |
| frozen | native-context-bare | gda (LATEST_GA_MODEL) | 272 | 57 | 3 | 3 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED) | 270 | 54 | 3 | 2 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | 272 | 54 | 3 | 4 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | 283 | 55 | 3 | 5 |
| frozen | native-context | gda (MODEL_UNSPECIFIED) | 263 | 52 | 3 | 4 |
| frozen | native-governed | gda (MODEL_UNSPECIFIED) | 222 | 18 | 5 | 0 |
| frozen | native-graph | gda (MODEL_UNSPECIFIED) | 190 | 42 | 4 | 7 |
| frozen | native-kc-max | gda (MODEL_UNSPECIFIED) | 274 | 60 | 3 | 4 |
| frozen | native-kc-reach | gda (MODEL_UNSPECIFIED) | 264 | 58 | 3 | 4 |
| frozen | native-kc | gda (MODEL_UNSPECIFIED) | 200 | 40 | 4 | 5 |
| frozen | native-mcp | claude-haiku-5-5 | 274 | 44 | 1 | 3 |
| frozen | native-mcp | claude-sonnet-5-5 | 288 | 70 | 0 | 4 |
| frozen | native-mcp | nemotron:free | 90 | 11 | 0 | 1 |
| frozen | native-shaped | gda (MODEL_UNSPECIFIED) | 196 | 47 | 3 | 1 |
| hard-v2 | native-bare | gda (MODEL_UNSPECIFIED) | 45 | 6 | 0 | 1 |
| hard-v2 | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | 45 | 13 | 0 | 0 |
| hard-v2 | native-context | gda (MODEL_UNSPECIFIED) | 45 | 13 | 0 | 0 |
| hard-v2 | native-kc-max | gda (MODEL_UNSPECIFIED) | 48 | 13 | 0 | 0 |
| hard | baseline | claude-haiku-5-5 | 79 | 20 | 2 | 3 |
| hard | cc-metricflow | cc (fresh-haiku) | 76 | 13 | 0 | 0 |
| hard | cc-metricflow | cc (fresh-opus) | 24 | 4 | 0 | 0 |
| hard | cc-metricflow | cc (fresh-sonnet) | 71 | 12 | 0 | 0 |
| hard | cc-metricflow | cc (haiku) | 21 | 2 | 0 | 0 |
| hard | cc-metricflow | cc (opus) | 24 | 3 | 0 | 0 |
| hard | cc-metricflow | cc (sonnet) | 23 | 6 | 0 | 0 |
| hard | custom-hybrid | claude-haiku-5-5 | 111 | 32 | 0 | 0 |
| hard | custom-hybrid | nemotron:free | 39 | 7 | 0 | 0 |
| hard | custom-metricflow | claude-haiku-5-5 | 101 | 28 | 0 | 0 |
| hard | custom-metricflow | claude-sonnet-5-5 | 80 | 22 | 0 | 0 |
| hard | custom-metricflow | nemotron:free | 102 | 14 | 0 | 1 |
| hard | custom-toolbox | claude-haiku-5-5 | 67 | 21 | 0 | 2 |
| hard | custom-toolbox | claude-sonnet-5-5 | 68 | 30 | 0 | 6 |
| hard | custom-toolbox | nemotron:free | 20 | 2 | 0 | 0 |
| hard | native-bare | gda (MODEL_UNSPECIFIED) | 92 | 12 | 0 | 0 |
| hard | native-context-bare | gda (LATEST_GA_MODEL) | 125 | 15 | 0 | 0 |
| hard | native-context-bare | gda (MODEL_UNSPECIFIED) | 126 | 14 | 0 | 0 |
| hard | native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | 125 | 24 | 0 | 1 |
| hard | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | 125 | 16 | 0 | 0 |
| hard | native-context | gda (MODEL_UNSPECIFIED) | 126 | 21 | 0 | 1 |
| hard | native-governed | gda (MODEL_UNSPECIFIED) | 95 | 5 | 0 | 0 |
| hard | native-graph | gda (MODEL_UNSPECIFIED) | 81 | 9 | 0 | 2 |
| hard | native-kc-max | gda (MODEL_UNSPECIFIED) | 122 | 11 | 0 | 1 |
| hard | native-kc-reach | gda (MODEL_UNSPECIFIED) | 118 | 16 | 0 | 1 |
| hard | native-kc | gda (MODEL_UNSPECIFIED) | 90 | 7 | 0 | 1 |
| hard | native-mcp | claude-haiku-5-5 | 114 | 31 | 0 | 0 |
| hard | native-mcp | claude-sonnet-5-5 | 84 | 32 | 0 | 4 |
| hard | native-mcp | nemotron:free | 42 | 9 | 0 | 0 |
| hard | native-shaped | gda (MODEL_UNSPECIFIED) | 90 | 14 | 0 | 0 |

### Check 3 per arm and model (number turns scored wrong, confident-wrong, declined or unclear)

| set | arm | model | not-right turns | flagged and read | scorer miss (confirmed) | genuine miss | unclear |
|---|---|---|---:|---:|---:|---:|---:|
| frozen | baseline | claude-haiku-5-5 | 103 | 15 | 10 | 5 | 0 |
| frozen | baseline | nemotron:free | 15 | 0 | 0 | 0 | 0 |
| frozen | cc-metricflow | cc (fresh-haiku) | 78 | 1 | 1 | 0 | 0 |
| frozen | cc-metricflow | cc (fresh-opus) | 13 | 0 | 0 | 0 | 0 |
| frozen | cc-metricflow | cc (fresh-sonnet) | 77 | 1 | 0 | 0 | 1 |
| frozen | cc-metricflow | cc (haiku) | 32 | 0 | 0 | 0 | 0 |
| frozen | cc-metricflow | cc (opus) | 28 | 0 | 0 | 0 | 0 |
| frozen | cc-metricflow | cc (sonnet) | 28 | 0 | 0 | 0 | 0 |
| frozen | cc-metricflow | cc (subject-haiku) | 29 | 0 | 0 | 0 | 0 |
| frozen | custom-hybrid | claude-haiku-5-5 | 55 | 14 | 12 | 0 | 2 |
| frozen | custom-hybrid | nemotron:free | 14 | 1 | 1 | 0 | 0 |
| frozen | custom-lightdash | nemotron:free | 17 | 0 | 0 | 0 | 0 |
| frozen | custom-metricflow | claude-haiku-5-5 | 53 | 8 | 5 | 0 | 3 |
| frozen | custom-metricflow | claude-opus-5-5 | 73 | 3 | 0 | 3 | 0 |
| frozen | custom-metricflow | claude-sonnet-5-5 | 73 | 8 | 3 | 2 | 3 |
| frozen | custom-metricflow | nemotron:free | 18 | 0 | 0 | 0 | 0 |
| frozen | custom-toolbox | claude-haiku-5-5 | 152 | 5 | 4 | 1 | 0 |
| frozen | custom-toolbox | claude-sonnet-5-5 | 156 | 4 | 3 | 1 | 0 |
| frozen | custom-toolbox | nemotron:free | 55 | 0 | 0 | 0 | 0 |
| frozen | native-bare | gda (MODEL_UNSPECIFIED) | 53 | 0 | 0 | 0 | 0 |
| frozen | native-context-bare | gda (LATEST_GA_MODEL) | 22 | 2 | 2 | 0 | 0 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED) | 24 | 2 | 2 | 0 | 0 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | 22 | 0 | 0 | 0 | 0 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | 11 | 1 | 1 | 0 | 0 |
| frozen | native-context | gda (MODEL_UNSPECIFIED) | 31 | 1 | 1 | 0 | 0 |
| frozen | native-governed | gda (MODEL_UNSPECIFIED) | 72 | 0 | 0 | 0 | 0 |
| frozen | native-graph | gda (MODEL_UNSPECIFIED) | 104 | 3 | 0 | 3 | 0 |
| frozen | native-kc-max | gda (MODEL_UNSPECIFIED) | 20 | 0 | 0 | 0 | 0 |
| frozen | native-kc-reach | gda (MODEL_UNSPECIFIED) | 30 | 0 | 0 | 0 | 0 |
| frozen | native-kc | gda (MODEL_UNSPECIFIED) | 94 | 2 | 0 | 2 | 0 |
| frozen | native-mcp | claude-haiku-5-5 | 20 | 11 | 10 | 0 | 1 |
| frozen | native-mcp | claude-sonnet-5-5 | 6 | 1 | 0 | 0 | 1 |
| frozen | native-mcp | nemotron:free | 8 | 1 | 1 | 0 | 0 |
| frozen | native-shaped | gda (MODEL_UNSPECIFIED) | 98 | 2 | 0 | 2 | 0 |
| hard | baseline | claude-haiku-5-5 | 47 | 10 | 5 | 5 | 0 |
| hard | cc-metricflow | cc (fresh-haiku) | 50 | 6 | 5 | 1 | 0 |
| hard | cc-metricflow | cc (fresh-opus) | 18 | 3 | 0 | 2 | 1 |
| hard | cc-metricflow | cc (fresh-sonnet) | 55 | 4 | 0 | 3 | 1 |
| hard | cc-metricflow | cc (haiku) | 21 | 1 | 0 | 1 | 0 |
| hard | cc-metricflow | cc (opus) | 18 | 2 | 0 | 2 | 0 |
| hard | cc-metricflow | cc (sonnet) | 19 | 2 | 0 | 2 | 0 |
| hard | custom-hybrid | claude-haiku-5-5 | 15 | 4 | 4 | 0 | 0 |
| hard | custom-hybrid | nemotron:free | 3 | 0 | 0 | 0 | 0 |
| hard | custom-metricflow | claude-haiku-5-5 | 25 | 9 | 9 | 0 | 0 |
| hard | custom-metricflow | claude-sonnet-5-5 | 46 | 6 | 0 | 3 | 3 |
| hard | custom-metricflow | nemotron:free | 24 | 4 | 3 | 0 | 1 |
| hard | custom-toolbox | claude-haiku-5-5 | 59 | 1 | 0 | 1 | 0 |
| hard | custom-toolbox | claude-sonnet-5-5 | 58 | 0 | 0 | 0 | 0 |
| hard | custom-toolbox | nemotron:free | 22 | 0 | 0 | 0 | 0 |
| hard | native-bare | gda (MODEL_UNSPECIFIED) | 34 | 0 | 0 | 0 | 0 |
| hard | native-context-bare | gda (LATEST_GA_MODEL) | 1 | 0 | 0 | 0 | 0 |
| hard | native-governed | gda (MODEL_UNSPECIFIED) | 31 | 0 | 0 | 0 | 0 |
| hard | native-graph | gda (MODEL_UNSPECIFIED) | 45 | 3 | 0 | 3 | 0 |
| hard | native-kc-max | gda (MODEL_UNSPECIFIED) | 1 | 0 | 0 | 0 | 0 |
| hard | native-kc-reach | gda (MODEL_UNSPECIFIED) | 8 | 0 | 0 | 0 | 0 |
| hard | native-kc | gda (MODEL_UNSPECIFIED) | 36 | 3 | 0 | 3 | 0 |
| hard | native-mcp | claude-haiku-5-5 | 12 | 4 | 4 | 0 | 0 |
| hard | native-mcp | claude-sonnet-5-5 | 1 | 0 | 0 | 0 | 0 |
| hard | native-shaped | gda (MODEL_UNSPECIFIED) | 36 | 3 | 0 | 3 | 0 |

### Check 4 per arm and model (ambiguous turns)

| set | arm | model | ambiguous turns | right | right only through ASKS_WHICH | right by a date-only carry | not right: one or two meanings, no question | not right: no meaning |
|---|---|---|---:|---:|---:|---:|---:|---:|
| frozen | baseline | claude-haiku-5-5 | 6 | 3 | 0 | 0 | 1 | 2 |
| frozen | baseline | nemotron:free | 2 | 1 | 0 | 1 | 1 | 0 |
| frozen | cc-metricflow | cc (fresh-haiku) | 6 | 5 | 0 | 0 | 1 | 0 |
| frozen | cc-metricflow | cc (fresh-opus) | 1 | 1 | 0 | 0 | 0 | 0 |
| frozen | cc-metricflow | cc (fresh-sonnet) | 6 | 5 | 0 | 0 | 1 | 0 |
| frozen | cc-metricflow | cc (haiku) | 2 | 2 | 0 | 0 | 0 | 0 |
| frozen | cc-metricflow | cc (opus) | 2 | 2 | 0 | 0 | 0 | 0 |
| frozen | cc-metricflow | cc (sonnet) | 2 | 2 | 0 | 0 | 0 | 0 |
| frozen | cc-metricflow | cc (subject-haiku) | 2 | 2 | 0 | 0 | 0 | 0 |
| frozen | custom-hybrid | claude-haiku-5-5 | 6 | 6 | 0 | 2 | 0 | 0 |
| frozen | custom-hybrid | nemotron:free | 2 | 2 | 0 | 0 | 0 | 0 |
| frozen | custom-metricflow | claude-haiku-5-5 | 6 | 5 | 0 | 0 | 1 | 0 |
| frozen | custom-metricflow | claude-opus-5-5 | 6 | 6 | 0 | 0 | 0 | 0 |
| frozen | custom-metricflow | claude-sonnet-5-5 | 6 | 6 | 0 | 0 | 0 | 0 |
| frozen | custom-metricflow | nemotron:free | 2 | 2 | 0 | 0 | 0 | 0 |
| frozen | custom-toolbox | claude-haiku-5-5 | 6 | 0 | 0 | 0 | 3 | 3 |
| frozen | custom-toolbox | claude-sonnet-5-5 | 6 | 0 | 0 | 0 | 3 | 3 |
| frozen | custom-toolbox | nemotron:free | 2 | 0 | 0 | 0 | 1 | 1 |
| frozen | native-bare | gda (MODEL_UNSPECIFIED) | 6 | 2 | 0 | 0 | 1 | 3 |
| frozen | native-context-bare | gda (LATEST_GA_MODEL) | 6 | 6 | 0 | 0 | 0 | 0 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED) | 6 | 6 | 0 | 0 | 0 | 0 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | 6 | 6 | 0 | 0 | 0 | 0 |
| frozen | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | 6 | 6 | 0 | 0 | 0 | 0 |
| frozen | native-context | gda (MODEL_UNSPECIFIED) | 6 | 6 | 0 | 0 | 0 | 0 |
| frozen | native-governed | gda (MODEL_UNSPECIFIED) | 6 | 6 | 0 | 0 | 0 | 0 |
| frozen | native-graph | gda (MODEL_UNSPECIFIED) | 6 | 3 | 0 | 0 | 2 | 1 |
| frozen | native-kc-max | gda (MODEL_UNSPECIFIED) | 6 | 4 | 0 | 0 | 2 | 0 |
| frozen | native-kc-reach | gda (MODEL_UNSPECIFIED) | 6 | 1 | 0 | 0 | 5 | 0 |
| frozen | native-kc | gda (MODEL_UNSPECIFIED) | 6 | 2 | 0 | 0 | 3 | 1 |
| frozen | native-mcp | claude-haiku-5-5 | 6 | 4 | 0 | 0 | 2 | 0 |
| frozen | native-mcp | claude-sonnet-5-5 | 6 | 6 | 0 | 0 | 0 | 0 |
| frozen | native-mcp | nemotron:free | 2 | 1 | 0 | 0 | 1 | 0 |
| frozen | native-shaped | gda (MODEL_UNSPECIFIED) | 6 | 0 | 0 | 0 | 4 | 2 |
| hard | baseline | claude-haiku-5-5 | 15 | 3 | 0 | 0 | 12 | 0 |
| hard | cc-metricflow | cc (fresh-haiku) | 15 | 6 | 0 | 0 | 9 | 0 |
| hard | cc-metricflow | cc (fresh-opus) | 5 | 2 | 0 | 0 | 3 | 0 |
| hard | cc-metricflow | cc (fresh-sonnet) | 15 | 6 | 0 | 0 | 9 | 0 |
| hard | cc-metricflow | cc (haiku) | 5 | 2 | 0 | 0 | 3 | 0 |
| hard | cc-metricflow | cc (opus) | 5 | 3 | 0 | 0 | 2 | 0 |
| hard | cc-metricflow | cc (sonnet) | 5 | 3 | 0 | 0 | 2 | 0 |
| hard | custom-hybrid | claude-haiku-5-5 | 15 | 6 | 0 | 0 | 9 | 0 |
| hard | custom-hybrid | nemotron:free | 5 | 2 | 0 | 0 | 3 | 0 |
| hard | custom-metricflow | claude-haiku-5-5 | 15 | 6 | 0 | 0 | 9 | 0 |
| hard | custom-metricflow | claude-sonnet-5-5 | 15 | 6 | 0 | 0 | 9 | 0 |
| hard | custom-metricflow | nemotron:free | 15 | 5 | 0 | 0 | 8 | 2 |
| hard | custom-toolbox | claude-haiku-5-5 | 15 | 0 | 0 | 0 | 15 | 0 |
| hard | custom-toolbox | claude-sonnet-5-5 | 15 | 3 | 0 | 0 | 12 | 0 |
| hard | custom-toolbox | nemotron:free | 5 | 0 | 0 | 0 | 4 | 1 |
| hard | native-bare | gda (MODEL_UNSPECIFIED) | 15 | 4 | 0 | 0 | 2 | 9 |
| hard | native-context-bare | gda (LATEST_GA_MODEL) | 14 | 7 | 0 | 0 | 7 | 0 |
| hard | native-context-bare | gda (MODEL_UNSPECIFIED) | 15 | 6 | 0 | 0 | 9 | 0 |
| hard | native-context-bare | gda (MODEL_UNSPECIFIED, FAST) | 15 | 8 | 0 | 0 | 7 | 0 |
| hard | native-context-bare | gda (MODEL_UNSPECIFIED, THINKING) | 15 | 8 | 0 | 0 | 7 | 0 |
| hard | native-context | gda (MODEL_UNSPECIFIED) | 15 | 5 | 0 | 0 | 10 | 0 |
| hard | native-governed | gda (MODEL_UNSPECIFIED) | 15 | 7 | 0 | 0 | 5 | 3 |
| hard | native-graph | gda (MODEL_UNSPECIFIED) | 15 | 2 | 0 | 0 | 10 | 3 |
| hard | native-kc-max | gda (MODEL_UNSPECIFIED) | 15 | 1 | 0 | 0 | 14 | 0 |
| hard | native-kc-reach | gda (MODEL_UNSPECIFIED) | 15 | 6 | 0 | 0 | 9 | 0 |
| hard | native-kc | gda (MODEL_UNSPECIFIED) | 15 | 4 | 0 | 0 | 10 | 1 |
| hard | native-mcp | claude-haiku-5-5 | 15 | 3 | 0 | 0 | 12 | 0 |
| hard | native-mcp | claude-sonnet-5-5 | 10 | 2 | 0 | 0 | 8 | 0 |
| hard | native-mcp | nemotron:free | 5 | 2 | 0 | 0 | 3 | 0 |
| hard | native-shaped | gda (MODEL_UNSPECIFIED) | 15 | 0 | 0 | 0 | 10 | 5 |
