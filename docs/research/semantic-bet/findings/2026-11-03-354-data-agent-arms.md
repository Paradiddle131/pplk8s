# The data-agent arms on the whole frozen set (#354, Q8)

## Question

Do the data-agent arms (`native-kc`, `native-shaped`, `native-graph`; `native-context` and `native-governed` have no agent yet) reach 3 runs of all 96 frozen cases under [RULE.md](../RULE.md) before the data agents' free trial ends, and which is the managed best?

## What was run

- 2026-11-03T11:46Z: `make gcp-cost-check` (ok, $0.000010 this month, the export until 07:48Z) and `make gcp-usage-check` (ok); the same at 11:48Z, unchanged.
- 2026-11-03T11:47Z: [`probes/328_mcp_live.py`](../probes/328_mcp_live.py) `--agent 354_data_agent.py --arm native-kc --runs 1 --requests 6` on `revenue_one_day` and the two-turn `followup_how_computed`, into a scratch log (not `eval-native-kc.jsonl`: a wiring check, not a pass).
  [`probes/354_data_agent.py`](../probes/354_data_agent.py) chats `bet-kc` as 327_kc_agent.py published it, every turn of a case in one stateless conversation (each `:chat` request carries the user's messages and every message the agent streamed back), and hands the turns to `semantic_agent.bet_live.run_live`, which scores them with `bet_eval.score_case` against `dbt_dev`'s expected numbers.

- 2026-11-03T11:49Z and 11:50Z, each after an ok `make gcp-cost-check` and `make gcp-usage-check` (the 11:49Z one after the 11:48Z checks; ok again after 11:50Z): `python3 -I probes/354_data_agent.py --legacy native-kc native-shaped native-graph` republished `bet-kc`, `bet-shaped` and `bet-graph` with their published context plus `legacy.channel_daily`, `legacy.country_sales` and `legacy.daily_net_sales`, as RULE.md wants for every SQL arm.

## Observed

- `measured` (the run above): `revenue_one_day` right ("total net revenue (excluding cancelled orders) was **€868.65**", its SQL over `silver.orders` with `LOWER(status) != 'cancelled'`); `followup_how_computed` turn 1 right (€964.19 on 1 October), turn 2 wrong under the rule (it explained its own SQL, "Sum of all order amounts in `pplk8s-lab-001.silver.orders` … excluding cancelled orders", rather than quoting the metric's definition), so the run is wrong.
- `measured`: the second turn answered about the first turn's €964.19 without being told it again, so the stateless history reaches the agent.
- 3 chats, no OpenRouter request.

- `measured` (the republish above): each agent read back with the legacy tables published beside its own: `bet-kc` and `bet-shaped` the seven silver tables plus the three legacy ones, `bet-graph` its three silver tables plus the three legacy ones (its graph and other context kept as published).
  Rerunning 327_kc_agent.py, 329_shaped_agent.py or 331_graph_agent.py republishes its agent without them; run `--legacy` again after.

## What it means for the verdict

Nothing yet: the passes are still to run.

## Still unknown

- The arms' numbers on the whole set.

## Sources

- `measured`: the runs above; probes `354_data_agent.py`, `328_mcp_live.py`.
