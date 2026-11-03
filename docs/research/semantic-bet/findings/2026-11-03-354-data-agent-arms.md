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

## What it means for the verdict

- A data agent's whole run of the set fits in about 16 minutes, so k = 3 on the three built data-agent arms takes about two and a half hours of passes, well before 2026-12-24.
- RULE.md compares arms on the same model, and a data agent answers only with Google's model: as written, the rule pairs no data-agent arm with ours, so the managed-best comparison needs the owner's call (#333).

## Still unknown

- `native-shaped` and `native-graph` on the whole set (`native-kc` is done).
- How the rule compares a managed arm (Google's model) with ours (a free OpenRouter model).

## Sources

- `measured`: the runs above; probes `354_data_agent.py`, `328_mcp_live.py`.
