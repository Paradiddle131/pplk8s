# native-context and native-governed on the whole frozen set (#355, Q8)

## Question

How do the two frozen data-agent arms #354 left unrun, `native-context` (the data agent with our generated context, PR #310) and `native-governed` (the data agent over the governed tables MetricFlow computed), do on all 96 frozen cases under [RULE.md](../RULE.md), beside `native-kc`, `native-shaped` and `native-graph`, and which data-agent arm is the managed best?

## What was run

- 2026-11-03T16:39Z: read back the main track's agents (read only): `pplk8s-semantic` (17 tables: `semantic.time_spine` and 16 `silver` tables; 64 verified queries, 71 glossary terms, a system instruction) and `pplk8s-governed` (24 `governed` tables and `semantic.time_spine`; 67 verified queries, 71 glossary terms).
- 2026-11-03T16:40Z, after an ok `make gcp-cost-check` ($0.000010 this month) and `make gcp-usage-check` at 16:39Z: `python3 -I probes/354_data_agent.py --copy native-context native-governed` created and published `bet-context` from `pplk8s-semantic`'s published context and `bet-governed` from `pplk8s-governed`'s, each plus `legacy.channel_daily`, `legacy.country_sales` and `legacy.daily_net_sales` (RULE.md's legacy schema), and read both back with those tables.
- 2026-11-03T16:41Z: `make services-up` and `DB=dbt_dev tests/e2e/agent-fixture.sh` for the expected numbers; `make gcp-cost-check` and `make gcp-usage-check` ok (BigQuery queries 65.15 GiB, 6.4% of the free tier).
- 2026-11-03T16:42Z to 17:12Z: two passes side by side, `328_mcp_live.py --agent 354_data_agent.py --arm <arm> --runs 3 --requests 200 --minutes 30` for each arm, into [`eval-native-context.jsonl`](../eval-native-context.jsonl) and [`eval-native-governed.jsonl`](../eval-native-governed.jsonl); both stopped `time`.
- 2026-11-03T17:12Z: `make gcp-cost-check` ($0.000010, unchanged) and `make gcp-usage-check` (ok, BigQuery queries 68.66 GiB, 6.7%); [eval.md](../eval.md) rewritten from every log.
- 2026-11-03T19:56Z, the next wake: `make services-up` and `DB=dbt_dev tests/e2e/agent-fixture.sh` again (the Compose stack had been recreated).
- 2026-11-03T20:00Z, after an ok `make gcp-cost-check` ($0.000010) and `make gcp-usage-check` (ok): the same two passes side by side, `--runs 3 --requests 220 --minutes 45`, 20:00Z to 20:26Z; `native-governed` stopped `done` (127 runs in 133 chats: all 3 runs of all 96 cases), `native-context` ended at 20:25Z on a `ConnectionResetError` mid-stream (103 runs in 111 chats), which `354_data_agent.py` now turns into a failed chat the runner asks again instead of the end of the pass.
- 2026-11-03T20:26Z: `make gcp-cost-check` ($0.000010, unchanged) and `make gcp-usage-check` (ok, BigQuery queries 71.29 GiB, 7.0%).
- 2026-11-03T20:30Z, after ok checks: `native-context`'s last 36 runs (36 chats, 20:30Z to 20:38Z) in a pass beside #357's two new arms (that finding has the window's checks after); [eval.md](../eval.md) rewritten from the five arms' logs at 20:39Z.

## Observed

- `measured` (the first wake's passes, 16:42Z to 17:12Z): `native-context` logged 149 runs in 159 chats, `native-governed` 161 runs in 173 chats: run 1 of all 96 cases each, and 53 and 65 runs of run 2; no 429 in either pass.
- `measured` (the logs then): `native-context` 133 right, 3 declined, 6 wrong, 6 confident-wrong, 1 unclear; `native-governed` 128 right, 23 declined, 7 wrong, 3 confident-wrong.
- `measured` (eval.md at 17:13Z, run 1, the only run all five data-agent arms shared then):

| | `native-context` | `native-governed` | `native-kc` | `native-shaped` | `native-graph` |
|---|---|---|---|---|---|
| Accuracy | 87.5% | 72.9% | 64.6% | 61.5% | 61.5% |
| Confident-wrong | 6.2% | 3.1% | 4.2% | 5.2% | 7.3% |
| `covered` (67) | 95.5% | 91.0% | 71.6% | 65.7% | 67.2% |
| `trap` (11) | 100.0% | 100.0% | 63.6% | 45.5% | 63.6% |
| `uncovered` (29) | 69.0% | 31.0% | 48.3% | 51.7% | 48.3% |
| `conversation` (7) | 71.4% | 71.4% | 57.1% | 28.6% | 42.9% |

- So on run 1 the managed best is `native-context`, 23 points above `native-kc`; `native-governed` is right on `covered` and `trap` cases nearly as often, and declines most `uncovered` ones (31.0% right there: declining is right only where the data can't answer).

- `measured` (the whole logs, 288 runs each, no 429 in this wake): `native-context` 251 right, 6 declined, 12 wrong, 15 confident-wrong, 4 unclear; `native-governed` 210 right, 54 declined, 15 wrong, 5 confident-wrong, 4 unclear.
- `measured` ([eval.md](../eval.md), all 3 runs of all 96 cases, every data-agent arm):

| | `native-context` | `native-governed` | `native-kc` | `native-shaped` | `native-graph` |
|---|---|---|---|---|---|
| Accuracy | 87.2% | 72.9% | 64.2% | 61.8% | 61.8% |
| Confident-wrong | 5.2% | 1.7% | 4.2% | 5.6% | 6.9% |
| pass^3 | 83.3% | 70.8% | 59.4% | 58.3% | 57.3% |
| `covered` (67) | 94.0% | 91.0% | 71.1% | 66.7% | 68.7% |
| `trap` (11) | 100.0% | 100.0% | 63.6% | 51.5% | 63.6% |
| `distractor` (3) | 100.0% | 100.0% | 88.9% | 77.8% | 100.0% |
| `uncovered` (29) | 71.3% | 31.0% | 48.3% | 50.6% | 46.0% |
| `conversation` (7) | 66.7% | 71.4% | 52.4% | 33.3% | 42.9% |
| `planted` (4) | 100.0% | 66.7% | 100.0% | 100.0% | 83.3% |

- `measured` (RULE.md's paired bootstrap, 10,000 resamples, seed 325, each arm minus `native-context`; descriptive, since all five are managed): accuracy `native-governed` −0.142 [−0.219, −0.073], `native-kc` −0.229 [−0.326, −0.135], `native-shaped` −0.253 [−0.351, −0.160], `native-graph` −0.253 [−0.351, −0.160], each a difference; confident-wrong `native-governed` −0.035 [−0.076, +0.000], `native-kc` −0.010 [−0.066, +0.042], `native-shaped` +0.003, `native-graph` +0.017, each no difference.
- So at k = 3 the managed best among all five data-agent arms (RULE.md § The rule, 1) is `native-context`, 87.2% right, ahead of every other data-agent arm by an interval that excludes zero; run 1's picture held over runs 2 and 3.
  #357's later arms, scored after this, put `native-context-bare` (89.6%) on top with no accuracy difference from `native-context` ([its finding](2026-11-03-357-equal-reach.md)); eval.md now shows all seven.

## What it means for the verdict

- The context we generate from the dbt project (PR #310: glossary terms, verified queries, a system instruction over `silver`) grounds Google's data agent far better than Knowledge Catalog's dbt import does, on all 3 runs of the frozen set (+0.229 accuracy, an interval excluding zero): the gap Knowledge Catalog's import leaves is real and measured, and a generator of data-agent context from MetricFlow is the strongest managed arm so far.
- Governed tables (MetricFlow's numbers precomputed) give the lowest confident-wrong rate of any data-agent arm (1.7% at k = 3; against `native-context` an interval that just reaches zero) at the cost of answering less outside them (31.0% right on `uncovered`, 54 of its 288 runs declined).

## Still unknown

- How much of `native-context`'s lead comes from its 64 verified queries resembling frozen questions and how much from its 16 `silver` tables against `bet-kc`'s 7: [#357](../../../../../../issues/357) measures both (`findings/2026-11-03-357-equal-reach.md`).
- How the rule compares these arms with ours (Google's model against a free OpenRouter one): #333's owner question.

## Sources

- `measured`: the runs above; probes `354_data_agent.py` (`--copy`), `328_mcp_live.py`; `bet-context` and `bet-governed` stay on the project for the next passes.
