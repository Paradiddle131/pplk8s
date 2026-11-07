# The data-agent arms on the whole frozen set (#354, Q8)

## Question

Do the data-agent arms (`native-kc`, `native-shaped`, `native-graph`; `native-context` and `native-governed` have no agent yet) reach 3 runs of all 96 frozen cases under [RULE.md](../RULE.md) before the data agents' free trial ends, and which is the managed best?

## What was run

- 2026-11-03T11:46Z: `make gcp-cost-check` (ok, $0.000010 this month, the export until 07:48Z) and `make gcp-usage-check` (ok); the same at 11:48Z, unchanged.
- 2026-11-03T11:47Z: [`probes/328_mcp_live.py`](../probes/328_mcp_live.py) `--agent 354_data_agent.py --arm native-kc --runs 1 --requests 6` on `revenue_one_day` and the two-turn `followup_how_computed`, into a scratch log (not `eval-native-kc.jsonl`: a wiring check, not a pass).
  [`probes/354_data_agent.py`](../probes/354_data_agent.py) chats `bet-kc` as 327_kc_agent.py published it, every turn of a case in one stateless conversation (each `:chat` request carries the user's messages and every message the agent streamed back), and hands the turns to `semantic_agent.bet_live.run_live`, which scores them with `bet_eval.score_case` against `dbt_dev`'s expected numbers.

- 2026-11-03T11:49Z and 11:50Z, each after an ok `make gcp-cost-check` and `make gcp-usage-check` (the 11:49Z one after the 11:48Z checks; ok again after 11:50Z): `python3 -I probes/354_data_agent.py --legacy native-kc native-shaped native-graph` republished `bet-kc`, `bet-shaped` and `bet-graph` with their published context plus `legacy.channel_daily`, `legacy.country_sales` and `legacy.daily_net_sales`, as RULE.md wants for every SQL arm.

- 2026-11-03T11:51Z to 12:11Z, after the 11:50Z checks: the first pass, `328_mcp_live.py --agent 354_data_agent.py --arm native-kc --runs 3 --requests 150 --minutes 20` into [`eval-native-kc.jsonl`](../eval-native-kc.jsonl); it stopped on its 20-minute cap.
  The pass logged each row's `model` as the runner's OpenRouter `MODEL_ID` though Google's model answers a data agent; the 112 rows were relabelled `google-data-agent (MODEL_UNSPECIFIED)` (nothing else changed), and the probe now names its model (`MODEL`), which the runner logs.

- 2026-11-03T12:41Z to 13:14Z, after an ok `make gcp-cost-check` and `make gcp-usage-check` at 12:38Z and 12:41Z (both ok and unchanged again at 13:14Z): the second pass, the same command with `--requests 200 --minutes 35`, on a fresh session's Compose warehouse (`make services-up`, then `DB=dbt_dev tests/e2e/agent-fixture.sh` for the expected numbers); it finished runs 2 and 3 (176 runs, 188 chats) and stopped `done`.

- 2026-11-03T13:38Z to 13:51Z, after an ok `make gcp-cost-check` and `make gcp-usage-check` at 13:38Z on a fresh session's Compose warehouse (`make services-up`, `DB=dbt_dev tests/e2e/agent-fixture.sh`): `native-shaped`'s first pass, `328_mcp_live.py --agent 354_data_agent.py --arm native-shaped --runs 3 --requests 200 --minutes 33` into [`eval-native-shaped.jsonl`](../eval-native-shaped.jsonl); it logged 59 runs and stopped `quota` on one chat's HTTP 429.
- 2026-11-03T13:52Z: the project's quotas for `geminidataanalytics.googleapis.com`, read with Service Usage's `consumerQuotaMetrics` (read-only).
- 2026-11-03T13:52Z to 14:16Z, after an ok `make gcp-cost-check` and `make gcp-usage-check` at 13:52Z (both ok and unchanged again at 14:16Z): `native-shaped`'s second pass, the same command with `--minutes 24`, with the probe retrying a throttled chat (below); it logged 148 runs and stopped `time`.

- 2026-11-03T14:41Z to 15:12Z, after an ok `make gcp-cost-check` and `make gcp-usage-check` at 14:40Z on a fresh session's Compose warehouse (`make services-up`, `DB=dbt_dev tests/e2e/agent-fixture.sh`), both ok and unchanged again at 15:12Z: two passes side by side, `native-shaped`'s third (`--runs 3 --requests 200 --minutes 20`, 14:41Z–14:56Z, stopped `done`) and `native-graph`'s first (`--runs 3 --requests 200 --minutes 30`, 14:41Z–15:11Z, stopped `time`), into [`eval-native-shaped.jsonl`](../eval-native-shaped.jsonl) and [`eval-native-graph.jsonl`](../eval-native-graph.jsonl).
- 2026-11-03T15:40Z to 16:10Z, after an ok `make gcp-cost-check` and `make gcp-usage-check` at 15:38Z on a fresh session's Compose warehouse (`make services-up`, `DB=dbt_dev tests/e2e/agent-fixture.sh`), both ok and unchanged again at 16:13Z: `native-graph`'s second pass, `--runs 3 --requests 200 --minutes 32`, into [`eval-native-graph.jsonl`](../eval-native-graph.jsonl); it stopped `done`.

## Observed

- `measured` (the run above): `revenue_one_day` right ("total net revenue (excluding cancelled orders) was **€868.65**", its SQL over `silver.orders` with `LOWER(status) != 'cancelled'`); `followup_how_computed` turn 1 right (€964.19 on 1 October), turn 2 wrong under the rule (it explained its own SQL, "Sum of all order amounts in `pplk8s-lab-001.silver.orders` … excluding cancelled orders", rather than quoting the metric's definition), so the run is wrong.
- `measured`: the second turn answered about the first turn's €964.19 without being told it again, so the stateless history reaches the agent.
- 3 chats, no OpenRouter request.

- `measured` (the republish above): each agent read back with the legacy tables published beside its own: `bet-kc` and `bet-shaped` the seven silver tables plus the three legacy ones, `bet-graph` its three silver tables plus the three legacy ones (its graph and other context kept as published).
  Rerunning 327_kc_agent.py, 329_shaped_agent.py or 331_graph_agent.py republishes its agent without them; run `--legacy` again after.

- `measured` (the pass above, [eval.md](../eval.md)): run 1 of all 96 cases and 16 of run 2 in 20 minutes, 118 chats, about 10 s a case; on run 1, `native-kc` is right on 64.6% of cases, confident-wrong on 4.2%; `covered` 71.6%, `trap` 63.6%, `uncovered` 48.3% (declining is right there), `conversation` 57.1%, `distractor` and `planted` 100% (3 and 4 cases).
  Over all 112 runs logged: 78 right, 24 declined, 6 wrong, 4 confident-wrong.

- `measured` (the second pass, [eval.md](../eval.md)): `native-kc` on all 3 runs of all 96 cases, 306 chats in all: accuracy 64.2%, confident-wrong 4.2%, pass^3 59.4%; `covered` 71.1%, `trap` 63.6%, `uncovered` 48.3%, `conversation` 52.4%, `distractor` 88.9%, `planted` 100%.
  Runs 2 and 3 alone: 107 right, 47 declined, 14 wrong, 8 confident-wrong of 176, so run 1's 64.6% held (the agent is stable across runs; pass^3 is 5 points under accuracy).
  `make gcp-usage-check`'s `Data agents tokens` line read 0 tokens before and after both passes, so its Monitoring source does not show these chats yet (a lag or a metric the chats don't write); cost stayed $0.000010.

- `measured` (the first pass above): the 429 that ended it read `{"error": {"code": 429, "message": "Request throttled at the client by AdaptiveThrottler.", "status": "RESOURCE_EXHAUSTED"}}` on `bet_cancellation_rate_period`, run 1, at 13:51Z, about 6 chats a minute; the probe called every 429 `daily_quota`, which ends a pass.
- `measured` (the quota read above): the Chat API allows 160 requests a minute per project and per user, the API 600 a minute per user and 1,800 per project, A2A 600 a minute per agent; there is no daily request cap, and every `Paid Input/Output Tokens` daily limit reads `-1` (unlimited).
  So that 429 was Google shedding load, not a spent quota: the probe now calls a 429 `rate_limit`, retries the chat after 15, 30 and 60 s (each attempt one request against `--requests`), and leaves a still-throttled run for a later pass instead of ending the pass.
  The second pass met no 429 (every run's chats equal its turns).
- `measured` (both passes, [eval.md](../eval.md)): `native-shaped` on runs 1 and 2 of all 96 cases and 15 of run 3, 207 runs and 219 chats: 132 right, 40 declined, 15 wrong, 12 confident-wrong, 8 unclear (awaiting the blind judge, wrong for now).
  On the two runs both arms finished, `native-shaped` against `native-kc`: accuracy 61.5% and 64.1%, confident-wrong 5.7% and 4.2%, pass^2 59.4% and 62.5%; `conversation` 28.6% and 57.1%, `covered` 66.4% and 70.9%, `trap` 54.5% and 59.1%, `uncovered` 50.0% and 48.3%, `distractor` 83.3% both, `planted` 100% both.
  The verified queries answer much of `native-shaped` (`matched_query` in its calls), and one of them misleads: `revenue_total` run 1 matched "revenue, returns and net revenue by day between a start date and an end date" and answered per day ("€981.69 … for October 1, 2026 … €868.65 … for October 2"), not the total, confident-wrong.

- `measured` (the side-by-side passes above): neither met a 429 (no `rate_limit` in either pass's output), at up to about 11 chats a minute together.
- `measured` (the passes above, [eval.md](../eval.md)): `native-shaped` on all 3 runs of all 96 cases (81 runs, 87 chats this pass; 288 runs and 306 chats in all): accuracy 61.8%, confident-wrong 5.6%, pass^3 58.3%, against `native-kc`'s 64.2%, 4.2% and 59.4%; `conversation` 33.3% and 52.4%, `covered` 66.7% and 71.1%, `trap` 51.5% and 63.6%, `uncovered` 50.6% and 48.3%, `distractor` 77.8% and 88.9%, `planted` 100% both.
  So the verified queries and governed views of #329 do not lift a data agent above the plain Knowledge Catalog context on this set; they cost it on follow-ups and traps.
- `measured` (the same passes): `native-graph` on run 1 of all 96 cases and 49 of run 2, 145 runs and 151 chats: 92 right, 35 declined, 6 wrong, 11 confident-wrong, 1 unclear; on run 1, accuracy 61.5% and confident-wrong 7.3%, against `native-kc`'s 64.6% and 4.2% and `native-shaped`'s 61.5% and 5.2%.
- `measured` (the same log): in none of `native-graph`'s 145 runs does its SQL name the graph (no `GRAPH_TABLE`, `MATCH` or `bet_graph` in any call); every answer it gave came from SQL over the silver or legacy tables, so the graph's measures beside the tables changed nothing it did (Q6).
- `measured` (the second pass above, [eval.md](../eval.md)): `native-graph` on all 3 runs of all 96 cases (143 runs, 155 chats this pass, no 429; 288 runs and 306 chats in all): accuracy 61.8%, confident-wrong 6.9%, pass^3 57.3%, against `native-kc`'s 64.2%, 4.2%, 59.4% and `native-shaped`'s 61.8%, 5.6%, 58.3%; `conversation` 42.9%, `covered` 68.7%, `trap` 63.6%, `uncovered` 46.0%, `distractor` 100%, `planted` 83.3%.
  This pass alone: 86 right, 38 declined, 10 wrong, 9 confident-wrong.
- `measured` (the whole log, 288 runs): still no call names the graph (`GRAPH_TABLE` and `bet_graph` appear 0 times), so Q6's live answer holds at k = 3: a data agent with a property graph beside the tables does not aggregate through it.
- `measured`: `make gcp-usage-check`'s `Data agents tokens` still read 0 after 918 chats across the three arms today, so that line cannot show the trial's use; cost stayed $0.000010.

## What it means for the verdict

- On Google's model, the plain Knowledge Catalog context (`native-kc`) is the managed best, all three built arms at k = 3: shaping (views, table functions, verified queries) and a graph with measures did not beat it, and both raised confident-wrong answers.

- A data agent's whole run of the set fits in about 16 minutes, so k = 3 on the three built data-agent arms takes about two and a half hours of passes, well before 2026-12-24.
- RULE.md compares arms on the same model, and a data agent answers only with Google's model: as written, the rule pairs no data-agent arm with ours, so the managed-best comparison needs the owner's call (#333).

## Still unknown

- `native-context` and `native-governed`: not run, no data agent was built for them.
- Whether `Data agents tokens` ever shows these chats (a Monitoring lag or a metric the Chat API doesn't write).
- How the rule compares a managed arm (Google's model) with ours (a free OpenRouter model).

## Sources

- `measured`: the runs above; probes `354_data_agent.py`, `328_mcp_live.py`.
