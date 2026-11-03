# The data-agent arms on the whole frozen set (#354, Q8)

## Question

Do the data-agent arms (`native-kc`, `native-shaped`, `native-graph`; `native-context` and `native-governed` have no agent yet) reach 3 runs of all 96 frozen cases under [RULE.md](../RULE.md) before the data agents' free trial ends, and which is the managed best?

## What was run

- 2026-11-03T11:46Z: `make gcp-cost-check` (ok, $0.000010 this month, the export until 07:48Z) and `make gcp-usage-check` (ok); the same at 11:48Z, unchanged.
- 2026-11-03T11:47Z: [`probes/328_mcp_live.py`](../probes/328_mcp_live.py) `--agent 354_data_agent.py --arm native-kc --runs 1 --requests 6` on `revenue_one_day` and the two-turn `followup_how_computed`, into a scratch log (not `eval-native-kc.jsonl`: a wiring check, not a pass).
  [`probes/354_data_agent.py`](../probes/354_data_agent.py) chats `bet-kc` as 327_kc_agent.py published it, every turn of a case in one stateless conversation (each `:chat` request carries the user's messages and every message the agent streamed back), and hands the turns to `semantic_agent.bet_live.run_live`, which scores them with `bet_eval.score_case` against `dbt_dev`'s expected numbers.

## Observed

- `measured` (the run above): `revenue_one_day` right ("total net revenue (excluding cancelled orders) was **€868.65**", its SQL over `silver.orders` with `LOWER(status) != 'cancelled'`); `followup_how_computed` turn 1 right (€964.19 on 1 October), turn 2 wrong under the rule (it explained its own SQL, "Sum of all order amounts in `pplk8s-lab-001.silver.orders` … excluding cancelled orders", rather than quoting the metric's definition), so the run is wrong.
- `measured`: the second turn answered about the first turn's €964.19 without being told it again, so the stateless history reaches the agent.
- 3 chats, no OpenRouter request.

## What it means for the verdict

Nothing yet: the passes are still to run.

## Still unknown

- RULE.md gives every SQL arm the `legacy` schema; `bet-kc`, `bet-shaped` and `bet-graph` were published with silver (and their own objects) only, so each needs republishing with `legacy` in reach, through its own probe, before a pass counts.
- The arms' numbers on the whole set.

## Sources

- `measured`: the runs above; probes `354_data_agent.py`, `328_mcp_live.py`.
