# native-context and native-governed on the whole frozen set (#355, Q8)

## Question

How do the two frozen data-agent arms #354 left unrun, `native-context` (the data agent with our generated context, PR #310) and `native-governed` (the data agent over the governed tables MetricFlow computed), do on all 96 frozen cases under [RULE.md](../RULE.md), beside `native-kc`, `native-shaped` and `native-graph`, and which data-agent arm is the managed best?

## What was run

- 2026-11-03T16:39Z: read back the main track's agents (read only): `pplk8s-semantic` (17 tables: `semantic.time_spine` and 16 `silver` tables; 64 verified queries, 71 glossary terms, a system instruction) and `pplk8s-governed` (24 `governed` tables and `semantic.time_spine`; 67 verified queries, 71 glossary terms).
- 2026-11-03T16:40Z, after an ok `make gcp-cost-check` ($0.000010 this month) and `make gcp-usage-check` at 16:39Z: `python3 -I probes/354_data_agent.py --copy native-context native-governed` created and published `bet-context` from `pplk8s-semantic`'s published context and `bet-governed` from `pplk8s-governed`'s, each plus `legacy.channel_daily`, `legacy.country_sales` and `legacy.daily_net_sales` (RULE.md's legacy schema), and read both back with those tables.
- 2026-11-03T16:41Z: `make services-up` and `DB=dbt_dev tests/e2e/agent-fixture.sh` for the expected numbers; `make gcp-cost-check` and `make gcp-usage-check` ok (BigQuery queries 65.15 GiB, 6.4% of the free tier).
- 2026-11-03T16:42Z to 17:12Z: two passes side by side, `328_mcp_live.py --agent 354_data_agent.py --arm <arm> --runs 3 --requests 200 --minutes 30` for each arm, into [`eval-native-context.jsonl`](../eval-native-context.jsonl) and [`eval-native-governed.jsonl`](../eval-native-governed.jsonl); both stopped `time`.
- 2026-11-03T17:12Z: `make gcp-cost-check` ($0.000010, unchanged) and `make gcp-usage-check` (ok, BigQuery queries 68.66 GiB, 6.7%); [eval.md](../eval.md) rewritten from every log.

## Observed

- `measured` (the passes above): `native-context` logged 149 runs in 159 chats, `native-governed` 161 runs in 173 chats: run 1 of all 96 cases each, and 53 and 65 runs of run 2; no 429 in either pass.
- `measured` (the whole logs): `native-context` 133 right, 3 declined, 6 wrong, 6 confident-wrong, 1 unclear; `native-governed` 128 right, 23 declined, 7 wrong, 3 confident-wrong.
- `measured` ([eval.md](../eval.md), run 1, the only run all five data-agent arms share yet):

| | `native-context` | `native-governed` | `native-kc` | `native-shaped` | `native-graph` |
|---|---|---|---|---|---|
| Accuracy | 87.5% | 72.9% | 64.6% | 61.5% | 61.5% |
| Confident-wrong | 6.2% | 3.1% | 4.2% | 5.2% | 7.3% |
| `covered` (67) | 95.5% | 91.0% | 71.6% | 65.7% | 67.2% |
| `trap` (11) | 100.0% | 100.0% | 63.6% | 45.5% | 63.6% |
| `uncovered` (29) | 69.0% | 31.0% | 48.3% | 51.7% | 48.3% |
| `conversation` (7) | 71.4% | 71.4% | 57.1% | 28.6% | 42.9% |

- So on run 1 the managed best is `native-context`, 23 points above `native-kc`; `native-governed` is right on `covered` and `trap` cases nearly as often, and declines most `uncovered` ones (31.0% right there: declining is right only where the data can't answer).

## What it means for the verdict

- The context we generate from the dbt project (PR #310: glossary terms, verified queries, a system instruction over `silver`) grounds Google's data agent far better than Knowledge Catalog's dbt import does, on run 1 of the frozen set: the gap Knowledge Catalog's import leaves is real and measured, and a generator of data-agent context from MetricFlow is the strongest managed arm so far.
- Governed tables (MetricFlow's numbers precomputed) give the lowest confident-wrong rate of any data-agent arm (3.1%) at the cost of answering less outside them.

## Still unknown

- Runs 2 and 3 of both arms (the next wakes' passes); pass^3 and the paired interval wait on them.
- How much of `native-context`'s lead comes from its 64 verified queries resembling frozen questions (RULE.md froze the set after PR #310 wrote them; the overlap is unchecked) and how much from its 16 `silver` tables against `bet-kc`'s 7 (the `uncovered` group's 69.0% hints at reach).
- How the rule compares these arms with ours (Google's model against a free OpenRouter one): #333's owner question.

## Sources

- `measured`: the runs above; probes `354_data_agent.py` (`--copy`), `328_mcp_live.py`; `bet-context` and `bet-governed` stay on the project for the next passes.
