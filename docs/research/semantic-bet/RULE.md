# The bet's eval rule

Frozen 2026-11-03 by #325, before any arm is scored.
It fixes the question set, the arms, how a run is scored and the rule that turns scores into the verdict, so the eval cannot be bent toward the answer we hope for.
The set is [`services/semantic-agent/evals/semantic_bet.yaml`](../../../services/semantic-agent/evals/semantic_bet.yaml); its SHA-256 at freezing is in [the finding](findings/2026-11-03-325-frozen-eval.md).

## What freezing means

- From the first scored run on, nobody edits the set's questions, expected SQL or groups, this rubric or this rule.
- A defect found later (an expected SQL that answers another question, a fixture row that makes a question unanswerable) retires the case, as § Retiring a defective case says (2026-11-06; before then it got a new dated set beside this one).
- A new arm may join later (Claude variants, an arm a register question adds); it is scored on this set under this rule, and the arms already scored are not rerun to suit it.

## Retiring a defective case

2026-11-06T13:09Z, the owner, in a session: "if you notice any errors on the questions, I'd rather them gone instead of claiming something that has flaws in the way we conduct these tests ... even if we collected a lot of data points on a given faulty test or question, together with your confirmation and agreement, I believe we would get rid of them if we're certain that otherwise we would have a dirty data points collected from faulty test situations".

- A case is defective when the test itself is wrong, whatever any arm does: its expected SQL answers another question than the one asked; its question has more than one reasonable reading and the case does not accept each; the fixture cannot support it (no rows, or an answer fixed by construction); or the scorer misjudges answers to it (a right answer it cannot read, or a wrong one it passes, such as a small whole number any answer may carry).
- Not a defect: an arm failing it, every arm passing it (a ceiling is a result), a setup that cannot reach its tables (a reach limit, reported and labelled as one), or a result that goes against what we expected.
- Each defect is written down with its evidence (the case, what is wrong, a reproduction on the fixture), judged on the case alone, by a reviewer who has not read the arms' results on it where that can be arranged, and retired only when the agent and the owner both confirm it.
- A retired case is listed in the register below with its date and evidence, and every set and version stops scoring it from then on: the two numbers, the groups, the comparisons, the criteria and the report.
  Its runs stay in the logs, never edited or deleted, so the retirement can be audited or undone; the report shows only scored questions and never mentions a retirement: no count, no reason, no register (owner, 2026-11-06, § Changes since freezing); the register, the logs and the findings keep the record.
- A set's file stays frozen: retiring is an entry in the register, not an edit of the set; a defect that a corrected case would fix goes into the next version as a new case.

The machine-readable register is [`redacted.jsonl`](redacted.jsonl) beside the logs (`semantic_agent.bet_eval.OVERLAY`): `case` rows retire a case, `run` rows redact one logged run (the runner then asks it again), `label` rows correct a group, and an `undo` row lifts one.
The evidence for every row below is in [the audit's reports](findings/382-case-audit/) (#382).

| Case | Set(s) | Retired | Class | Defect |
|---|---|---|---|---|
| `bet_applicants_reaching_interview` | frozen | 2026-11-06 | expected_sql | expects 2/3 because dbt_dev's candidate snapshot holds only each candidate's last stage (#383); K-002 reached interview, so the business answer is 3/3 |
| `bet_median_days_to_interview` | frozen | 2026-11-06 | expected_sql | its expected number rests on one candidate because the stage history is missing in dbt_dev (#383) |
| `bet_weekday_most_orders` | frozen | 2026-11-06 | fixture | every weekday has exactly 24 orders by construction: no unique answer |
| `bet_wetter_day_nl_orders` | frozen | 2026-11-06 | fixture | both days have 2.40 mm of rain and 3 Dutch orders: no unique answer; 63 runs carried 3 by chance |
| `bet_most_email_opens` | frozen | 2026-11-06 | fixture | three customers tie at one open each |
| `bet_peak_page_view_hour` | frozen | 2026-11-06 | fixture | 09:00 and 10:00 tie at two page views |
| `bet_istanbul_warmer` | frozen | 2026-11-06 | fixture | the weather formula makes the difference exactly 8 every day |
| `bet_customers_september` | frozen | 2026-11-06 | fixture | 10 is every base customer; the cancelled filter the trap tests changes nothing |
| `bet_customers_over_three_orders` | frozen | 2026-11-06 | fixture | 10 is every customer who ordered, by construction |
| `bet_median_days_lead_to_booking` | frozen | 2026-11-06 | fixture | every booking is 5 hours after its lead: 0 days by construction |
| `bet_delivery_calls_per_100_shipped` | frozen | 2026-11-06 | fixture | rests on one model-labelled delivery call; the expected 2 is carried by chance |
| `amsterdam_temperature` | frozen | 2026-11-06 | fixture | 11.00 by the fixture's formula, near Amsterdam's October norm: a climate guess passes |
| `monthly_active_customers` | frozen | 2026-11-06 | fixture | the 28-day window holds every customer who ever acted: vacuous |
| `bet_median_days_to_hire` | frozen | 2026-11-06 | readings | two hires, so the median equals the governed mean (a covered metric) and whole days give 6, which fails |
| `bet_p75_reply_hours` | frozen | 2026-11-06 | readings | four values: the common percentile methods give 10, 7 or 16 |
| `bet_p90_order` | frozen | 2026-11-06 | readings | interpolated 158.125 against nearest-rank 158.00, outside the tolerance |
| `bet_median_session_minutes` | frozen | 2026-11-06 | readings | 1.5 with one-event sessions as 0 minutes, 6 without them; only 1.5 accepted |
| `bookings_wow_growth` | frozen | 2026-11-06 | readings | 'how much did bookings grow' also reads as +3 bookings, which the case does not accept |
| `time_to_hire` | frozen | 2026-11-06 | readings | calendar days give 6.0, which fails against 6.0833 |
| `returns_amount` | frozen | 2026-11-06 | readings | written when 'early October' meant 1-2 October (24.75); fixture_weeks.sql later added returns on 5-6 October and the expected number moved to 89.75 |
| `hard_happiest_call_topic` | hard, hard-v2 | 2026-11-06 | fixture | 0.75 by construction in every period and reading |
| `hard_orders_last_fiscal_quarter` | hard, hard-v2 | 2026-11-06 | fixture | 217 is every order row: no fiscal boundary falls inside the data |
| `hv2_first_order_value_october` | hard-v2 | 2026-11-06 | readings | 'the first week of October' reads as 1-7 Oct (36.5), 5-11 Oct (42.5) or the week holding 1 Oct (32.0); only 36.5 accepted |
| `hard_active_customers_week` | hard, hard-v2 | 2026-11-09 | expected_sql | the governed "Active customers" (`customers_distinct`) makes 10 the answer, but the case wants 10 and 9 or a question back ([finding](findings/2026-11-09-434-retire-active-customers-week.md), #434) |
| `bet_median_order_september` | frozen | 2026-11-09 | readings | 110 orders: only the interpolated 117.375 is accepted; `percentile_disc` gives 116.75 and the governed median a middle amount ([sweep](findings/2026-11-09-437-case-sweep.md), #437) |
| `bet_peak_checkout_hour` | frozen | 2026-11-09 | fixture | two checkouts in the window, both at 09:00: 2 is every checkout by construction ([sweep](findings/2026-11-09-437-case-sweep.md), #437) |

Confirmed by the owner, 2026-11-06, in a session: "Retire all, make sure the final report doesn't care about what happened earlier and uses the latest the freshest data points only".
`hard_active_customers_week` confirmed by the owner, 2026-11-09, in a session (on #434): "retire the case".
`bet_median_order_september` and `bet_peak_checkout_hour` confirmed by the owner, 2026-11-09, in a session (on #437): "retire what's needed". The frozen set then scores 74 cases, 13 of them `uncovered` (17.6%).
After these retirements the frozen set scores 76 cases, 15 of them `uncovered` (19.7%, under § The set's 30%): its uncovered group is reported with its n and this reason, and a later version on a richer fixture rebuilds it.

## The set

| Group | What it holds | Why |
|---|---|---|
| `covered` | questions a metric of the semantic layer answers | where a semantic layer should win |
| `trap` | covered questions whose obvious SQL over the trusted tables gives another number (the set's `naive_sql` per question, checked to differ on the fixture) | definitions the schema cannot show (#314) |
| `distractor` | covered questions where a legacy table in reach gives another number (`legacy.*`, #185) | the wrong-table failure |
| `uncovered` | questions no metric covers, written blind from the business description (the finding says how) | where a semantic layer refuses and SQL can still answer |
| `conversation` | follow-ups, "how was that computed", ambiguous terms | what a chat adds |
| `planted` | rows holding instructions | safety, reported, never deciding |

At least 30% of the cases are `uncovered`; a case may be in `trap` or `distractor` and `covered` at once.
Every case keeps `questions.yaml`'s shape, so `services/semantic-agent`'s eval can load it; the groups sit in the file's `groups` map.

2026-11-03, [#356](../../../../../issues/356): a second set, [`services/semantic-agent/evals/semantic_bet_hard.yaml`](../../../services/semantic-agent/evals/semantic_bet_hard.yaml) (43 cases, 44% `uncovered`; SHA-256 in [its finding](findings/2026-11-03-356-hard-set.md)), is an addition the owner asked for, not a correction: "were the agents asked such hard questions, difficult to measure and easy to fail due to the complexity of the business query, as well as the lack of knowledge around the terms? If not, I would really like to … add hard queries and measure accordingly" (owner, 2026-11-03).
It is scored beside the first set under this same rule (outcomes, the two numbers, the paired comparison, the ladder), each set reported on its own, and it is frozen from now on, before any arm runs on it, as § What freezing means says of the first.

### Set versions

2026-11-06T09:18Z, [#376](../../../../../issues/376) (epic [#375](../../../../../issues/375)), written before any `hard-v2` case is drafted.
The owner, 2026-11-06, in a session: "I wish the hard set was indeed harder, not only on the business side ... but also on the writing the SQL part"; "I don't want to lose the version 1 ... on the report ... I would show only the latest version"; "before replacing the version 1 with the version 2 on the report, you need to first prove it to me".

- A set version is a new set name and a new file, never an edit of a frozen one: `hard` is the hard set's v1 (`semantic_bet_hard.yaml`), `hard-v2` its v2 (`semantic_bet_hard_v2.yaml`).
  Each version keeps its own logs (`eval-hard-*.jsonl`, `eval-hard-v2-*.jsonl`) and its own rows in `results.json`; a superseded version's file, logs and rows are never edited or deleted.
- A version's file names what it supersedes (`supersedes: hard`) and why; this section gets one dated line per version.
- A version is frozen, as § What freezing means says, before any arm runs on it; its drafting never reads any arm's result, and no arm's result ever edits it.
  A criterion below that fails is a result, reported as one, never a reason to change the frozen set; a later version may follow, under this same rule.
- Carried runs: at a version's freeze, a script copies the superseded version's runs of each case whose scoring inputs are byte-identical (its question turns, expected SQL, hedges and tolerance) into the new version's logs.
  Each copied run carries `carried_from: <the superseded set>` and the SHA-256 of those scoring inputs; the copy is refused for any case whose hash differs, so only new or changed cases need new runs.
- The report shows one version of each set family by default: the superseded one until the owner says go on the new one's comparison, then the newest.
  The other stays in the data and in an appendix (or a set switch labelled superseded), with the same numbers as before.

#### `hard-v2` (2026-11-06)

`hard-v2` supersedes `hard`: v1 was hard on business language (jargon, fiscal and relative periods, implicit definitions, ambiguity), but most of its `uncovered` cases are a ratio or difference of two measures, arithmetic over metric results, so the set never tested writing SQL.
It holds v1's 43 cases byte-identical in their scoring inputs, relabelled under its groups, plus about 20 new cases drafted blind in a business user's words.

- Its groups: `covered` (one metric query answers it, unchanged); `composable` (no single metric does, but arithmetic over at most three metric query results does: a ratio, a difference, a share of two metric totals); `uncovered` (needs row-level SQL that no metric composition gives: a median, a percentile, time between events, a cohort, a ranking with ties, an anti-join, a date spine).
  At least 30% of its cases are `composable` or `uncovered`, and § The rule's "`uncovered` case" reads, on this set, as either of the two.
- Its kind `sql_hard` (a kind, not a group): the obvious SQL gives another number for a reason in the rubric below; it can sit on a `covered`, `composable` or `uncovered` case.
  `trap`, `conversation` and v1's kinds keep their v1 meaning.
- The SQL-difficulty rubric, fixed before drafting; every new case carries at least one: a join that fans out (orders to returns, sessions to events) and double counts; a distinct count across a join; a ratio of sums against a mean of ratios; a window (rank with ties, running totals, lag between events, the first event per customer); a median or a percentile; sessionization or gaps and islands; a cohort or retention over two periods; an anti-join ("customers who never ..."); a date spine (days with no orders count as zero); a fiscal calendar or a timezone boundary combined with any of the above.
- Hardness is shown without any agent: each new case's `naive_sql` (the obvious query) must give a number outside the tolerance from its `expected_sql`, checked by `probes/325_check_set.py`, as v1's traps were.

The pre-registered criteria, written 2026-11-06T09:18Z before any run on `hard-v2` and before its drafting; v2 is "harder on SQL" when all of these hold on its new cases at k = 3:

1. Agent-independent: every new case's naive SQL misses its expected number, and each case carries a rubric kind (the checker's output in the freeze finding).
2. The best SQL writer is off the ceiling: the managed best (`native-context-bare`, Gemini, thinking) is right on at most 85% of v2's new `uncovered` cases (it was 100% on v1's).
3. The inversion is gone: `custom-metricflow` on the free model answers fewer of v2's `uncovered` cases than of the frozen set's (38%).
4. The floor feels it: the bare data agent (`native-bare`) is at least 15 points below the managed best on v2's new cases.

Exploratory, reported with no pass or fail, since it is the hypothesis rather than a property of the set: whether context and tools (MetricFlow, the hybrid, catalog context) beat the floor on the `sql_hard` cases.
What to expect, written before any run: pure MetricFlow (`custom-metricflow`) should decline most of the `uncovered` group by design, its value showing on `covered` and `sql_hard` cases where the metric hides the tricky SQL; the hybrid and the SQL-writing arms are what the `uncovered` group tests.
The comparison of v1 and v2 on these criteria ([#380](../../../../../issues/380)) comes before the report shows `hard-v2` in v1's place ([#381](../../../../../issues/381)).

Frozen 2026-11-06T09:33Z by [#377](../../../../../issues/377), before any arm ran on it: [`services/semantic-agent/evals/semantic_bet_hard_v2.yaml`](../../../services/semantic-agent/evals/semantic_bet_hard_v2.yaml), 58 cases (v1's 43 unchanged, 15 new; 33 `composable` or `uncovered`), its SHA-256 and the checker's output in [its finding](findings/2026-11-06-377-hard-set-v2.md).

## The arms

The arms of [the register](README.md#the-arms), each built by its own issue: `native-context`, `native-governed`, `native-kc`, `native-shaped`, `native-graph`, `native-mcp`, `custom-metricflow`, `custom-metricflow-compute` (#400), `custom-toolbox`, and `baseline` (the reference, text-to-SQL that reads the generated docs).
Every arm that writes SQL is given the `legacy` schema beside the trusted layers (#185), with the descriptions it already carries ("replaced by …"); an arm that cannot read it (`custom-metricflow`) says so in the report.
An arm is scored with each model it is run with, and every comparison names each arm's model (§ The rule, 2, changed 2026-11-03 by #359).
The reach policy (2026-11-09T10:44Z, [#445](../../../../../issues/445), [#436](../../../../../issues/436)): every setup that writes SQL reaches the row-level data Google's data agents and `native-mcp` reach: `agent_sql`, the role of `baseline` and of `custom-hybrid`'s fallback, reads `silver` as `agent_metrics` does, column by column (the personal columns stay refused), and the fiscal calendar (`semantic.time_spine`), granted in the fixture's database only (`tests/e2e/agent-fixture.sh`) and checked by `probes/388_parity.py --grants`; `native-mcp` keeps `BET_SQL_DENY` unset.
The MetricFlow setups stay metrics-only by design: their declines on a case no metric covers are labelled reach limits ([#446](../../../../../issues/446)).
Runs logged with that reach carry `"reach": "silver"`; `baseline` and `custom-hybrid` are asked again, k = 3, on the cases the new reach touches ([#448](../../../../../issues/448)), and the runs before stay in the logs.
The owner's decision, 2026-11-09, in a session (recorded on #445): option (a), grant `agent_sql` read access to `silver`, so the baseline and the hybrid's SQL fallback reach the row-level data `native-mcp` and Google's data agents reach; and for #436, the fiscal calendar under the same policy, since the native setups read it (`native-context` publishes `semantic.time_spine`, `native-mcp` reads the `semantic` dataset; the parity finding).

## Scoring a run

Each case is asked `k = 3` times per arm and model (#184), each run in a fresh session, the turns of a conversation in one session.
Each turn of a run gets one outcome:

- **right**: the answer carries an expected number in one of the forms the eval accepts today (`evaluation.py`: within its tolerance, a rate also as a percentage), or for a `define` turn quotes the definitions, or for an `ambiguous` turn asks which meaning or gives every number.
- **declined**: no number, and it says it cannot answer, that nothing defines it, or asks a question back.
- **confident-wrong**: a number outside tolerance, with no statement in the same answer that it is uncertain, partial, an estimate, or not from governed definitions (a decline in the same answer, "no metric covers it, but …", is such a statement).
- **wrong**: any other answer (a number outside tolerance with such a statement, or no number and no decline).

The code decides where it can ([`semantic_agent/bet_rule.py`](../../../services/semantic-agent/src/semantic_agent/bet_rule.py), #340): the number parses (the eval's own parser), and a hedge is one of the phrases in the set's `hedges` list, matched case-insensitively.
Where the code cannot decide (no number parses but the answer is not a decline, or a hedge is phrased outside the list), a blind judge decides twice: a free model shown the question, the expected number and the answer, never the arm; two equal verdicts stand, two different ones make the turn **unclear**, counted as wrong and listed in the report.
The judge is Claude Haiku through `claude -p` (one fresh process a verdict, no tool, no MCP server, no settings, nothing kept), the free OpenRouter judge behind a switch (`--judge-backend openrouter`); only the current judge's verdicts are applied (2026-11-09, #427, § Changes since freezing).
A run of a case is right when every turn is right; it is confident-wrong when any turn is.

On an `uncovered` case, only the number is right: a decline is not right, and not confident-wrong either.
So a semantic layer that refuses honestly loses accuracy there and keeps its confident-wrong rate, and the report shows both.

## The two numbers per arm

- **Accuracy:** the mean over cases of the share of an arm's runs that are right.
- **Confident-wrong rate:** the mean over cases of the share of its runs that are confident-wrong.
- Reported beside them, never deciding: pass^3 (cases right in all three runs), each group's accuracy, the requests spent.

## Comparing two arms

- Paired by case: per case, arm B's share right minus arm A's (and the same for confident-wrong).
- A percentile bootstrap 95% interval of the mean difference, resampling cases, 10,000 resamples, seed 325.
- An interval that excludes zero is a difference; one that includes zero is **no difference**.
- With the set's size and three runs, the smallest accuracy difference this detects four times in five is in the finding (the power check); a smaller true difference will mostly read as no difference, and the report says so beside every tie.

## The cost ladder (a tie goes to the cheaper rung)

1. A Google-managed agent with configuration only: `native-context`, `native-kc`.
2. A managed agent over warehouse objects we generate and keep: `native-governed`, `native-shaped`, `native-graph`.
3. Our agent on managed or generated tools: `native-mcp`, `custom-toolbox`.
4. Our agent on our own semantic-layer server: `custom-metricflow`.

Within a rung, the arm with the fewer moving parts named in its finding wins a tie.

## The rule

1. Take the best arm on rung 1 or 2 by accuracy, on the model it runs with (the **managed best**).
2. Pair arms by case across models, each arm's model named: the managed best on its model (a data agent answers only with Google's) against each arm of ours on each model it ran with, on the cases both reached, each case's share over that arm's finished runs.
   An arm on rung 3 or 4 is worth building only if, against the managed best, its accuracy difference excludes zero above it, or its accuracy shows no difference and its confident-wrong rate's difference excludes zero below it.
   The pair with ours on the lab's own model (the free OpenRouter model the lab runs it on) decides; the same arm of ours on Claude is the check: a verdict that moves with the model says the gap is at least partly the model's, and the report says so beside the verdict.
3. Otherwise the verdict adopts the cheapest arm that shows no accuracy difference from the best arm overall, and names what the others would add.
4. The groups explain the verdict (where an arm wins or loses), and never overturn it: a win on `trap` alone is a reason the report names, not a rule.
5. Every comparison the report shows besides these is descriptive.

## Changes since freezing

- 2026-11-03 (#359, before the cross-model comparison was first scored): § The arms and § The rule, 1 and 2, compare a managed arm on Google's model with ours on its model, each arm's model named, instead of arms on the same model only, since no data agent can run on our model.
  The owner's answer, on [#333](../../../../../issues/333) (option C), 2026-11-03T19:02Z, in a session: "for #333 I can provide both Google AI Studio key of mine as well as Anthropic key with your help. option C makes sense".
  The Gemini same-model check was later dropped ([#362](../../../../../issues/362), owner, 2026-11-03): Claude stands in as the second-model check.
- 2026-11-03 (#360, #363): two arms join under § What freezing means (a new arm is scored on the sets under this rule; the arms already scored are not rerun): `native-kc-max` on rung 1 (the Knowledge Catalog arm with every free piece of context the lab can attach: BigQuery descriptions and a glossary linked to its columns, [#360](../../../../../issues/360)) and `custom-lightdash` on rung 4 (an ADK agent on Lightdash's free metric query API, a self-hosted semantic-layer server like MetricFlow's, [#363](../../../../../issues/363)).
- 2026-11-04 ([#372](../../../../../issues/372), [#373](../../../../../issues/373)): two arms join under § What freezing means: `native-bare` on rung 1 (a data agent over copies of `native-kc-max`'s tables with no catalog link, no description and no authored context: the floor every other arm is read against) and `custom-hybrid` on rung 4 (the semantic agent's MetricFlow tools plus a read-only SQL fallback for what no metric covers, its answer then saying so).
  The owner's words, 2026-11-04, in a session: "do we have a baseline? like a native agent with given nothing at all other than the tables on BQ" and "you can add such a hybrid setup: MetricFlow tools plus SQL fallback".
- 2026-11-04 ([#374](../../../../../issues/374)): `cc-metricflow` joins as a descriptive setup, outside § The rule's decision: the semantic agent's three MetricFlow tools called by a Claude Code subagent (Haiku, Sonnet, Opus on the owner's subscription) instead of the ADK agent, scored under § Scoring a run like any arm; its harness differs, its isolation is by instruction only, and a batch of cases shares one session, so the report shows it beside `custom-metricflow` and never as the arm that decides.
  The owner's words, 2026-11-04, in a session: "I know it's not the same thing as an API running our eval runs, but can you utilize background agents in parallel using our three different models here to test those eval scenarios".
- 2026-11-03 ([#367](../../../../../issues/367)): § Scoring a run's code learns the decline and scope-caveat wordings the logs show; the set's `hedges` list is unchanged.
  Two declines the blind judge found the code missing join `bet_rule.NOT_IN_DATA` ("is not tracked or available in the governed tables"; "there is no allocated budget column or budget table present in the schema to compute the remaining budget"), as "not tracked" and "no … column, table or field … to compute, calculate or determine", so a figure beside them is wrong (hedged) and one without a number declined, by the code.
  Scope caveats ("cannot split", "cannot filter", "covers all", "not broken down by") join the judge's `HEDGE_LIKE` candidates: a figure for a wider scope than asked, said to be so, goes to the judge, which decides whether it is hedged.
  Every log is scored on read under the current wordings, the live arms' included, without rewriting a line (`bet_eval.recode`); the local log is rescored (`--rescore`).
- 2026-11-03 ([#368](../../../../../issues/368)): the code reads typographic apostrophes (’ and ‘) as `'` before it matches a decline, a listed hedge or a hedge-like phrase (`bet_rule.fold`), so "can’t" reads as "can't"; every log is scored on read again, and no turn moved.
- 2026-11-03 ([#356](../../../../../issues/356), before the hard set is first scored): both sets decide.
  The frozen set and the hard set each go through § The rule on their own; the verdict holds where the two agree.
  Where they disagree, the cheaper rung wins, as a tie does (§ The cost ladder): an arm of ours is worth building only if step 2 holds on both sets, and the arm the verdict adopts in step 3 must show no accuracy difference from the best arm on both; the report names the disagreement and the groups that drive it.
  Why: the hard set detects about 15 points at k = 3 against the frozen set's 10 (findings/2026-11-03-356-hard-set.md), so its most likely disagreement is a difference it is too small to see; reading that as a tie keeps the two sets from cancelling into no verdict.
  Written 2026-11-03T22:15Z, before any comparison on the hard set was computed or read.
  The owner's answer, 2026-11-03, in a session: "#356: which question set does the verdict rest on? we can go both as you recommended".
- 2026-11-06 ([#382](../../../../../issues/382), the owner's go, in a session: "Fix scorer + redact"): § Scoring a run's code reads an answer's numbers past the eval's parser, the same for every arm and set, and scores every log again on read in full from each case's expected numbers, cached once from the fixture (`expected.json`, `bet_eval --write-expected`).
  - Dates and times written as models write them ("Oct 2", "Sept 30", "Sep 21–27", ISO dates with any hyphen, clock times) carry no number.
  - Number words ("Nine customers", "half"), whole percentages that round to the rate ("about 33%") and the answer's first "N of M" share carry the expected number.
  - "no … metric" with several words between is a decline.
  - A right turn whose expected number is a whole number of 40 or less, or one the question holds, stands by the code only as the answer's first figure in an answer that does not also decline; otherwise the blind judge decides.
  - A `define` turn that does not quote the definition word for word goes to the blind judge, shown the definition, instead of being wrong.
  - Why: the blind audit found that the scorer passed answers carrying a small expected number by chance (a day, an ID, a count of something else) and failed right answers in words or whole percentages (`findings/382-case-audit/`). Every audited miss now reads right, the 121 audited chance carries are redacted (§ Retiring a defective case), and the eval's own scorer (`evaluation.carries`, the main track's) is unchanged.
- 2026-11-06T18:40Z ([#388](../../../../../issues/388), [#387](../../../../../issues/387), before any of their runs): the Claude Code setups are two, each mirroring an arm tool for tool, and every Claude Code run goes through the strict headless runner: one `claude -p` process a run, a fresh session, no built-in tool (no shell, file or web tool), only the setup's MCP tools, the arm's own ADK instruction as the system prompt, and a deterministic audit of its transcript.
  - `cc-metricflow` mirrors `custom-metricflow`: `list_metrics`, `describe_metric`, `query_metrics` from `semantic_agent.mcp_server`, under `toolset_metricflow.INSTRUCTION`; its strict runs take new model labels (`claude-code-strict (<model>)`) beside the subagent rows already logged.
  - `cc-native-mcp` mirrors `native-mcp`: Google's BigQuery and Knowledge Catalog MCP tools, filtered to `probes/328_mcp_agent.py`'s 16 read-only names and behind the same cost guard (project pinned, dry run under 10 MiB), under that probe's instruction.
  - No tool-less variant: with no way to query, it could only decline or invent a number, which measures nothing the bet asks.
  - The audit fails a run that called a tool outside its setup's list or any built-in tool, and such a run is redacted as a test fault in `redacted.jsonl`, the same check on every Claude Code setup; a figure in the answer that no tool result holds, and a tool call written as text without a real call, are reported beside the run and scored as given.
  - Both stay descriptive, outside § The rule's decision, as `cc-metricflow` was: their harness is Claude Code's, not ADK's.
  - Every setup's tools and context, verified from code, logs and BigQuery's job history, are in [the parity finding](findings/2026-11-06-388-setup-parity.md); `semantic_agent.bet_tools` holds the declared lists, and both runners refuse to score a run whose calls fall outside its list.
  - The owner's words, 2026-11-06, in a session: "running tools or commands in the terminal must be considered as cheating and must not be included in the results"; "we must check and enforce all these deterministically as much as possible"; on the names, the `-strict` suffix is dropped from the setups and kept for the runner and its labels.
- 2026-11-06T20:39Z ([#394](../../../../../issues/394)): retired questions leave the report entirely; § Retiring a defective case's report clause changes from "says how many cases are retired and links the register, and says so beside any verdict a retirement moved" to: the report shows only scored questions and mentions no retirement, not even beside a verdict.
  Scores do not move: a retired question was already out of every number; the register, the logs, `redacted.jsonl` and the findings keep every retirement, auditable and undoable.
  The owner's words, 2026-11-06, in a session, on #394's recommendation: "Remove retired questions entirely, as recommended. Make sure nothing is left from such a thing that we are removing ... I said just cleanup, remove cleanly. no clutter".
- 2026-11-06T21:57Z ([#400](../../../../../issues/400)): two setups join under § What freezing means, before any run: `custom-metricflow-compute`, `custom-metricflow`'s agent and tools with one change to its instruction (`toolset_metricflow.INSTRUCTION_COMPUTE`): a figure may be plain arithmetic (a sum, difference, ratio or share) over numbers `query_metrics` returned in the turn, a rate over a span is a sum over a sum, and the answer names the figures and the operation; never an estimated or recalled figure, another definition or SQL; and `cc-metricflow-compute`, the same instruction from the strict headless Claude Code runner, descriptive like `cc-metricflow`.
  Why: the managed agents compute their figures in the SQL they write, and the governed one is told to "select, filter and add up" metric numbers and take a ratio as a sum over a sum (`dbt/scripts/build_catalog.py`, `GOVERNED_INSTRUCTION`; the parity finding: one SQL query a chat, no Python step); `custom-metricflow`'s "never compute" made its score count how often a model broke the instruction (Haiku 64%, Sonnet 52%, Opus 42% right on hard-v2 through Claude Code; through the metrics only 33%, 29%, 36%).
  `custom-metricflow` and `cc-metricflow` stay as they are, with every run; the scoring rule is unchanged (the number is scored), and the transcript audit still lists every figure no tool result holds.
  The owner's words, on #400, 2026-11-06T21:06Z: "could be A. as long as we double checked what the Google's native agent setup ... and the constraints, conditions, etc. there and confirm it'd match what we set up on the other envs"; "if we keep both the current tests and add the new version as different set up with slightly different conditions ... it sort of make sense to have them"; and in a session: "if we let metric flow setups do some arithmetic in a way that the native agents would have done anyways, I think it makes sense".
- 2026-11-07T08:50Z ([#400](../../../../../issues/400)): the page's "MetricFlow on the free model" (the headline, the winners' contrast, the strip and the forest lines) reads `custom-metricflow-compute` on each set once its free-model runs cover that set, and `custom-metricflow` until then; `custom-metricflow` stays on the page as a variant with every run (`report/build.py`, `HEADLINE_MF`).
  Why: the setup with arithmetic plays the same game as the managed agents, which compute their figures in their SQL, so it is the like-for-like comparison.
  The owner's words, on #400, 2026-11-06T23:24Z, to "should the page's headline 'MetricFlow on the free model' read this setup instead of `custom-metricflow`?": "yes"; and in a session, 2026-11-07: "I agree. we can replace."
- 2026-11-07T10:20Z: one setup joins under § What freezing means, before any run: `native-context-python` (rung 1, agent `bet-context-python`), `native-context`'s published context with one change: the agent's `options.analysis.python.enabled` is on, so its loop may run Python on its query results (Google's "Python analysis"); its tables, verified queries, glossary, instruction and byte cap are `bet-context`'s (`probes/354_data_agent.py --copy native-context-python`).
  Its log names every Python step as a `python_analysis` call with its code, and its declared tools are the data agents' plus that one (`semantic_agent/bet_tools.py`); the scoring rule is unchanged.
  Order: the extended hard set at k = 1, then the frozen set at k = 1, then k = 3 if the first round shows a difference worth its runs.
  Why: every data agent so far ran with Python off (the parity finding); whether Google's Python step changes accuracy or confident-wrong answers is a question the work platform will face.
  The owner's words, 2026-11-07, in a session, on the recommendation to add it: "go for native-context-python".
- 2026-11-09T10:29Z ([#427](../../../../../issues/427), [#426](../../../../../issues/426), epic [#424](../../../../../issues/424)): the blind judge of § Scoring a run is Claude Haiku through `claude -p` on the owner's subscription, not a free OpenRouter model: one fresh headless process a verdict with no tool, no MCP server, no settings and no saved session (`bet_eval.claude_judge`, the strict runner's flags less its tools), the judge prompt as its system prompt, two verdicts a turn as before; the OpenRouter judge stays behind `--judge-backend openrouter`.
  The verdict's `judge` field names the judge (`claude -p (haiku)`), so the two judges' verdicts never mix; only the current judge's are applied, and the Nemotron rows stay in `judge.jsonl` as history.
  A spent subscription limit stops a judge pass and scores no turn.
  The judge now asks about the turns the report leaves unclear, scored as the report scores them (`bet_eval.scored_logs`, from the cached expected numbers): before, it re-read the logs without them, so 408 of 416 unclear turns never reached it and counted as wrong.
  Why: the 2026-11-09 audit found the OpenRouter judge to be the larger sibling of the model answering every daily setup, and its requests spent the free quota the passes need.
  Every judgeable answer is judged once by Haiku ([#428](../../../../../issues/428)); an answer with Haiku's verdicts is never asked again unless a full refresh is asked for (the cache key holds the answer's hash and the judge).
  Haiku also judges the Claude Code rows Haiku answered; the owner accepts that as negligible.
  The owner's decision, 2026-11-09, in a session (recorded on #424): Claude Haiku through `claude -p` is the default judge, the OpenRouter judge behind a switch, and the free OpenRouter quota goes to answering questions, not judging.
- 2026-11-09T10:39Z ([#435](../../../../../issues/435)): on an `ambiguous` turn whose readings differ only in their dates (a relative date such as "the last 7 days"), a figure that matches one accepted reading is right when the answer names that reading's dates: its first and last day, or its last day as the end of the seven days ("the seven days to 1 October"); an unstated pick, or a window that matches no reading (an eight-day window), stays wrong.
  The rule is `bet_rule.stated_reading`, its readings `bet_rule.DATE_READINGS`, keyed by the turn's question; it touches one case, `hard_last_seven_days` (`hard` and `hard-v2`: 24-30 September or 25 September-1 October); no other relative-date case is `ambiguous` in any set, and `hard_ambiguous_q3` (a calendar or a fiscal quarter, not a relative date) is left to #436 and #437.
  Every log is scored again on read; on that case 84 runs on `hard` and 93 on `hard-v2` move from wrong to right, every one of them a stated reading, and the eight-day and unmatched windows stay wrong.
  Why: no setup's instruction asks for both readings of a relative window, and § Retiring a defective case calls a case defective when it does not accept each reasonable reading.
  The owner's decision, 2026-11-09, in a session (recorded on #435): accept a stated reading on every ambiguous relative-date case, not this one only.
- 2026-11-09T10:53Z ([#430](../../../../../issues/430)): on an `ambiguous` turn, asking which meaning is meant counts only when the asking sentence names one of the case's readings (`bet_rule.asks_which`, the words of each reading in `bet_rule.READING_WORDS`): a sentence that ends in "?" or offers another reading ("let me know if you meant fiscal Q3") names one; any "... or ...?" sentence ("do you want me to retry, or wait?") no longer counts, and an offer without a question mark now does.
  An ask beside a figure counts only when the figure is one reading's: an answer that picks an eight-day window and offers the seven-day one stays wrong.
  The main track's eval keeps its `ASKS_WHICH`; a turn with no listed readings keeps it here too.
  Every log is scored again on read; 21 turns move, 20 from wrong to right (`hard_ambiguous_q3` 9, `hard_real_revenue` 8, `ambiguous_customers`, `ambiguous_sales` and `hard_sales_germany_this_month` 1 each, every one an offer naming the other reading) and 1 from right to wrong (a `hard_sales_germany_this_month` run whose only question asked whether to retry a failing tool).
  Why: the 2026-11-09 audit found clarifying asks scored by punctuation, a real offer ("Let me know if you meant fiscal Q3.") wrong for its missing "?", and any "or" question right beside a wrong number.
- 2026-11-09T10:55Z ([#431](../../../../../issues/431)): every setup gets the same hedge rules.
  `custom-hybrid`'s required opener for a fallback answer, "Not a governed metric:", labels the answer and no longer hedges its figure by itself (`bet_rule.without_opener`); a fallback figure is hedged only by a doubt or scope the answer states, as any setup's is, and "not a governed metric" said in prose still hedges.
  The judge's hedge-like candidates (`HEDGE_LIKE`) add a rounded figure ("about"), "regardless of", a missing dimension ("no ... dimension") and "not the ... figure", so a confident-wrong turn with such a caveat goes to the blind judge, which decides whether it is hedged.
  Every log is scored again on read: three `custom-hybrid` turns on `hard-v2` move from wrong to confident-wrong (their only hedge was the opener), and 65 confident-wrong turns (frozen 4, hard 28, hard-v2 33) go to the judge.
  Why: the 2026-11-09 audit found the hybrid's fallback could never be confident-wrong, while other setups' explicit scope caveats scored confident-wrong.
- 2026-11-09T11:24Z ([#446](../../../../../issues/446)): every case carries a machine-checked reach map (`semantic_agent.bet_reach`): the tables its expected SQL reads, each in a setup's declared reach or rebuilt from `silver` sources that are (dbt's lineage, cached in `lineage.json`), and for the MetricFlow setups the groups a metric answers (`covered`, with `composable` for the setups with arithmetic).
  A case out of a setup's reach is a reach limit: its runs stay scored, `results.json` lists it under the set's `reach_limits`, and the page draws a dashed box round its runs with a tooltip; a setup whose reach is not declared there (`native-governed`, `custom-toolbox`) is unlabelled.
- 2026-11-09T11:24Z ([#450](../../../../../issues/450)): a setup's numbers read complete rounds only: each case counts its first r finished runs, r the fewest any of its cases has (`bet_eval.round_outcomes`), so a pass cut mid-round never averages cases over different run counts or makes pass^3 easier; the runs past the last complete round stay in the logs and are counted in `results.json` (`runs_beyond_rounds`); step two reports each pair's run count on the paired cases (`paired_runs`).
- 2026-11-09T11:27Z ([#447](../../../../../issues/447)): § The rule, 2 is also read on the cases both setups of a pair can reach (`bet_eval.step_two` with `bet_reach`'s limits): `results.json` keeps that reading beside each pair (`step_two[].reachable`), and the page says it beside the paired comparison; the verdict still reads every case, as § The rule, 2 says, and the reachable reading explains how much of a gap is reach.
- 2026-11-09T11:37Z ([#448](../../../../../issues/448)): a reach change supersedes, never redacts: a `reach` row in `redacted.jsonl` names the setups, model and cases the new reach touches, and their runs logged without that reach (`"reach": "silver"`) leave the scores and the resume, so those runs are asked again under the new reach; they stay in the logs, and an `undo` row lifts the change.
  The first: `baseline` and `custom-hybrid` on the free model, on the cases whose expected SQL needs `silver` or the fiscal calendar (frozen 34, hard 17, hard-v2 28), k = 3; their Claude rows keep their earlier reach (the Claude API lane is closed).
- 2026-11-09T11:37Z ([#443](../../../../../issues/443)): a run that calls outside its setup's tools is asked again once; its second fault is logged as its outcome, wrong, every turn wrong, with the calls named (`bet_tools.FAULT_TRIES`), so asking until a compliant answer appears cannot select the answers.
- 2026-11-09T11:37Z ([#459](../../../../../issues/459), [#457](../../../../../issues/457)): a case-run has a wall clock (`BET_CASE_TIMEOUT_S`, 600 s, beside the model call's own timeout); a run that stalls is asked once more, then logged as an error row.
  The two-error rule, as the code has held it since 2026-11-03: a run that errors `MAX_ERRORS` (2) times is scored wrong; an error retried and answered leaves no trace in the scores, and the reports list only errors with no later answer.
