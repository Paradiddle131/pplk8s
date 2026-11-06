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
  Its runs stay in the logs, never edited or deleted, so the retirement can be audited or undone; the report says how many cases are retired and links the register, and says so beside any verdict a retirement moved.
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

Confirmed by the owner, 2026-11-06, in a session: "Retire all, make sure the final report doesn't care about what happened earlier and uses the latest the freshest data points only".
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

The arms of [the register](README.md#the-arms), each built by its own issue: `native-context`, `native-governed`, `native-kc`, `native-shaped`, `native-graph`, `native-mcp`, `custom-metricflow`, `custom-toolbox`, and `baseline` (the reference, text-to-SQL that reads the generated docs).
Every arm that writes SQL is given the `legacy` schema beside the trusted layers (#185), with the descriptions it already carries ("replaced by …"); an arm that cannot read it (`custom-metricflow`) says so in the report.
An arm is scored with each model it is run with, and every comparison names each arm's model (§ The rule, 2, changed 2026-11-03 by #359).

## Scoring a run

Each case is asked `k = 3` times per arm and model (#184), each run in a fresh session, the turns of a conversation in one session.
Each turn of a run gets one outcome:

- **right**: the answer carries an expected number in one of the forms the eval accepts today (`evaluation.py`: within its tolerance, a rate also as a percentage), or for a `define` turn quotes the definitions, or for an `ambiguous` turn asks which meaning or gives every number.
- **declined**: no number, and it says it cannot answer, that nothing defines it, or asks a question back.
- **confident-wrong**: a number outside tolerance, with no statement in the same answer that it is uncertain, partial, an estimate, or not from governed definitions (a decline in the same answer, "no metric covers it, but …", is such a statement).
- **wrong**: any other answer (a number outside tolerance with such a statement, or no number and no decline).

The code decides where it can ([`semantic_agent/bet_rule.py`](../../../services/semantic-agent/src/semantic_agent/bet_rule.py), #340): the number parses (the eval's own parser), and a hedge is one of the phrases in the set's `hedges` list, matched case-insensitively.
Where the code cannot decide (no number parses but the answer is not a decline, or a hedge is phrased outside the list), a blind judge decides twice: a free model shown the question, the expected number and the answer, never the arm; two equal verdicts stand, two different ones make the turn **unclear**, counted as wrong and listed in the report.
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
