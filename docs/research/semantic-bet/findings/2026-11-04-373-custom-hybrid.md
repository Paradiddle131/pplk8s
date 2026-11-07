# custom-hybrid: MetricFlow first, a SQL fallback for what no metric covers (#373)

Question: does our agent close its only gap (the `uncovered` questions, where `custom-metricflow` declines by design and the data agents write SQL) when it may fall back to SQL and say the number is not governed?

## What was run

- `semantic_agent.hybrid` (MetricFlow's tools plus the baseline's read-only `execute_sql` over gold, exposed and `legacy`; the metrics-only instruction with its SQL ban and its decline replaced by the fallback, whose answer opens "Not a governed metric:", a listed hedge), built 2026-11-04 with `tests/test_hybrid.py`; frozen before any scored run (RULE.md § Changes since freezing, 2026-11-04).
- `DBT_HOST=localhost DBT_PORT=5433 MODEL_BACKEND=anthropic MODEL_ID=claude-haiku-5-5 python -m semantic_agent.bet_eval --runs 3 --arms custom-hybrid --dollars 2`, 18:28Z to about 18:50Z: all 288 runs of the frozen set, $0.4945 (ledger row `#373 frozen haiku custom-hybrid`).
- A first smoke at 18:25Z ran with no `DBT_HOST`: its three runs, and an Opus pass's, hit an unwritten audit row and are quarantined in `2026-11-04-audit-refused.jsonl` (never scored).

## What was observed (`measured`, results.json at 2026-11-04T18:55Z, before the judge decides the hybrid's unclear turns)

| Haiku, frozen set, k = 3 | Accuracy | Confident-wrong | `uncovered` (29) | `covered` (67) |
|---|---|---|---|---|
| `native-mcp` | 89.2% | 3.8% | 89.7% | 89.1% |
| `custom-metricflow` | 81.2% | 2.4% | 43.7% | 97.5% |
| `custom-hybrid` | 75.7% | 4.2% | 47.1% | 88.1% |

- The fallback is rarely taken: on `uncovered` cases 14 of 87 runs answered "Not a governed metric:" (12 right, 1 wrong, 1 declined); 30 runs still declined as the metrics-only agent does.
- On the other groups (191 runs), 11 runs used the fallback where a metric existed, all of them right; 11 runs were confident-wrong and 13 wait for the blind judge (counted wrong until judged), which is most of the drop from 97.5% to 88.1% on `covered`.

## What it means for the verdict

- As built, the hybrid does not close the gap: the model keeps the metrics-first habit and declines; its metric answers do worse than the metrics-only agent's (88.1% against 97.5% on `covered`) (11 confident-wrong, 13 unjudged, none through the fallback).
- The ADK agent on Google's MCP servers (`native-mcp`), which reads the catalog's definitions and writes SQL for everything, is the arm of ours that ties the managed best on the frozen set (results.json `step_three`).
- Not tuned after this result (the arm stays as frozen); a better prompt or a router is a new arm, scored under the rule like any other.

## Still unknown

- The judge's verdicts on the 15 unclear turns (after OpenRouter's 00:00Z reset).
- The hybrid on the hard set and on the free model (the completion plan's lanes).
