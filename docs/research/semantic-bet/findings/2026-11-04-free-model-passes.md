# The free model's day: the judge's backlog, `custom-metricflow` on both sets, and the rule's deciding pair

Question: with the OpenRouter free quota reset (1,000 a day, shared), does the rule's deciding pair, `custom-metricflow` on the free model against the managed best, reach a verdict on both sets ([`RULE.md`](../RULE.md) § Changes since freezing, [#356](../../../../../../issues/356)), and what do the waiting turns get from the blind judge?

## What was run

All on 2026-11-04, from `services/semantic-agent` on the train's `c7a0585`, `DBT_DBNAME=dbt_dev` (the Compose warehouse read under the shared warehouse lock, never rebuilt), every pass under the OpenRouter lock; the free count is `GET /api/v1/key`'s `data.free_model_daily_requests.used`, which trails the requests by about a minute.

| Pass (UTC) | Command | Requests (logged) | Free count used, before → after |
|---|---|---|---|
| 00:13 to 00:26 | `bet_eval --judge`, then `--set hard --judge` (twice: the first hard pass was cut at the 10-minute bound mid-way) | 98 verdicts (78 frozen, 20 hard), plus failed attempts | 0 → 96 |
| 00:27 to 00:39 | `bet_eval --arms custom-metricflow --runs 1 --minutes 7.5 --requests …`, two chunks: frozen set, run 1 finished | 175 (49 case-runs) | 96 → 270 |
| 00:39 to 01:13 | the same with `--set hard --runs 3`, five chunks: the hard set, all three runs | 502 (129 case-runs) | 270 → 743 |
| 01:14 to 01:24 | `--judge` and `--set hard --judge` on the turns these passes added | 4 sent, 0 answered: the judge model failed upstream | 743 → 776 |
| 01:24 to 01:27 | frozen set, run 2 (`--runs 2 --requests 55`) | 55 (14 case-runs) | 776 → 810 |

- In all, 830 logged requests, plus the judge's failed attempts; the free count read 831 of 1,000 at 01:28Z (`measured`), inside the lane's 850.
- The judge model (`nvidia/nemotron-3-ultra-550b-a55b:free`) failed every request from 01:14Z: one direct probe at 01:24Z gave `litellm.APIError: OpenrouterException - upstream request failed` after two retries (`measured`); `judge_turns` skips a failed request and goes on, so a pass in that state spends retries and writes nothing.
- `eval.md`, `eval-local.md` and `eval-hard-local.md` were regenerated after every pass and again with `--report-only` on both sets at 01:27Z.

## What was observed

`custom-metricflow` on `nvidia/nemotron-3.5-super-vl:free` (`measured`, each case's share over its finished runs, percentile bootstrap 95% over cases, seed 325):

| Set | Cases, runs | Accuracy | Confident-wrong | By group | Run outcomes |
|---|---|---|---|---|---|
| frozen | 96, 110 (run 1 of all, run 2 of 14) | 81.2% [72.9, 88.5] | 0.0% | 100% on `covered` (67), `trap` (11), `distractor`, `conversation`, `planted`; 37.9% on `uncovered` (29) | 92 right, 14 declined, 2 wrong, 2 unclear |
| hard | 43, 129 (k = 3) | 73.6% [61.2, 84.5] | 7.0% [2.3, 12.4] | `covered` 83.3% (24), `trap` 100% (6), `uncovered` 61.4% (19), `conversation` 58.3% (8) | 95 right, 13 declined, 11 wrong, 9 confident-wrong, 1 unclear |

- On the frozen set the 49 cases asked today were the set's tail, nearly all `uncovered` ones: the 95.1% of the first 47 cases fell to 81.2% over all 96 as the rule predicted ([#341](2026-11-03-341-local-arms.md)), and the free model still never gave a confident wrong number there.
- `eval.md`'s free-model table on the frozen set still reads 95.1% for `custom-metricflow`: it scores only the 41 cases every arm on that model reached (`baseline` and `custom-lightdash` were not run today), so the rule's lines below, which pair each arm on all its finished runs, are the numbers to use.
- The judge's 98 verdicts moved the Claude rows that were waiting (`measured`, `eval.md` before and after): on the frozen set Haiku's `custom-metricflow` accuracy 77.8% → 81.2% and `baseline` confident-wrong 10.4% → 6.6%, Sonnet's `custom-metricflow` 74.0% → 74.7%; on the hard set Haiku's confident-wrong `baseline` 11.6% → 7.8% and `custom-metricflow` 10.1% → 9.3%, Sonnet's 7.0% → 5.4%; `native-context`'s frozen confident-wrong 5.2% → 5.6%.
- Waiting for the judge (`eval.md`): 2 frozen turns (`bet_median_days_to_hire`, `bet_peak_checkout_hour`, run 1) and 1 hard turn (`hard_cart_abandonment`, run 3), all `custom-metricflow` on the free model: 6 requests once the judge model answers again.

## What the rule now says (`eval.md`, 01:27Z)

- The frozen set's managed best: `native-context-bare` on Google's model, 89.6%.
  `custom-metricflow` on the free model (decides), 96 of 96 cases, 110 runs: accuracy -0.083 [-0.149, -0.017], confident-wrong -0.045 [-0.087, -0.010]: not worth building.
  Its confident-wrong rate is lower by an interval that excludes zero, but the rule counts that only when accuracy shows no difference, and accuracy is lower.
- The hard set's managed best: `native-context` on Google's model, 87.1% (scored on run 1 of 31 of 43 cases; its runs are still partial, 85 of 129).
  `custom-metricflow` on the free model (decides), 43 of 43 cases, 129 runs: accuracy -0.182 [-0.295, -0.089], confident-wrong +0.070 [+0.023, +0.124]: not worth building.
- On both sets: "`custom-metricflow` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building."
  The checks on Claude Haiku and Sonnet read the same on both sets, so the verdict does not move with the model.

## What it means for the verdict

- The deciding pair now has a verdict on both sets for the first time, and it is "not worth building": against a data agent given our generated context, our MetricFlow agent on the free model is less accurate on both sets, and on the hard set also more often confidently wrong.
- Its one edge is on the frozen set: no confident wrong number in 110 runs, against 4.5% for the managed best, an interval that excludes zero; the rule as frozen weighs it only at equal accuracy.
- What it loses is what a metric-only agent should lose: questions no metric covers (37.9% right on the frozen set's `uncovered`), where the managed agent writes SQL.

## Still unknown

- The frozen set's runs 2 and 3 of `custom-metricflow` on the free model (82 of 96 cases of run 2 and all of run 3 left, about 690 requests at 3.7 a case-run): the pair uses one to two runs a case there.
- The hard set's managed best is on a partial run; a full `native-context` run could move the hard set's interval.
- The three turns waiting for the judge, and whether the judge model's upstream failure is transient.

## Sources

- `docs/research/semantic-bet/eval.md`, `eval-local.jsonl`, `eval-hard-local.jsonl` and `judge.jsonl` at this branch's head (`measured`).
- The free count, `GET https://openrouter.ai/api/v1/key` (`data.free_model_daily_requests`), read before and after every pass (`measured`).
