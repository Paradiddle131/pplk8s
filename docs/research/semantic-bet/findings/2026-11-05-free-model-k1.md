# The free model's lane at k = 1: the hybrid, then Google's MCP servers (#373, #333)

Question: on the free model that decides (RULE.md § The rule), how do the passes still missing from it score at one run a case, before the lane goes to k = 3 (owner, 2026-11-04T20:15Z: "we should absolutely start with k is equal to 1")?

## What was run

- `probes/lanes/free_lane.sh` from the 00:00Z reset of 2026-11-05 (OpenRouter free count 0 of 1,000, the lane's cap 850): `custom-hybrid` on the frozen set, then the hard set, with the judge after each pass; the GCP cost and usage gate; then `native-mcp` on the frozen set and the hard set.
- Model `nvidia/nemotron-3.5-super-vl:free` through OpenRouter, `DBT_HOST=localhost DBT_PORT=5433`, canary first (both passes answered it).
- Two container restarts (about 23:30Z and 00:10Z) cut the first start of the frozen pass; the lane resumed from its log, so the cut cost only the case-runs in flight.
- `custom-hybrid` frozen: 00:14Z to 00:29Z, exit 3 (all 96 cases answered; one run's model call failed with an OpenRouter transfer error and stays unscored); hard: 00:35Z to 00:50Z, exit 0; the free count was 665 after both and the judges.

## A fault the lane found, fixed

- `bet_eval` wrote `eval.md` and `results.json` at its own pass's k, so the k = 1 frozen pass cut every other arm to run 1 in `results.json` (written 00:28Z: the data agents read 96 runs where their logs hold 288).
- Fixed in `bet_eval.main` (it now writes at the rule's k, as `328_mcp_live.py` already did), with a test that fails on the old line; `results.json` was regenerated from the logs at 00:33Z and the hard pass, started after the fix, left the other arms whole.

## What was observed (`measured`, results.json at 2026-11-05T00:50Z; the free model at k = 1)

| Free model, k = 1 | Frozen: right | Frozen: confident-wrong | Frozen `uncovered` right | Hard: right | Hard: confident-wrong | Hard `uncovered` right |
|---|---|---|---|---|---|---|
| `custom-hybrid` (MetricFlow first, SQL fallback) | 85.4% [78.1, 91.7] | 1.0% [0.0, 3.1] | 52% | 86.0% [74.4, 95.3] | 0.0% | 84% |
| `custom-metricflow` (metrics only, for reference) | 81.2% [72.9, 88.5] | 0.0% | 38% | 73.6% [61.2, 84.5] | 7.0% | 61% |
| The managed best (data agent, generated context, `THINKING`, k = 3) | 94.8% | 1.0% | | 95.3% | 0.0% | |

- On the free model the hybrid is right more often than the metrics-only agent on both sets, the gain sitting in the `uncovered` questions (52% against 38% on the frozen set, 84% against 61% on the hard set) while `covered` and `trap` stay at 100% and 88% to 100%.
- It is still below the managed best on both sets (about 9 points on each); at k = 1 the intervals are wide, so k = 3 decides.
- On Claude Haiku through ADK the same hybrid scored below the metrics-only agent (75.7% against 81.2% on the frozen set, `findings/2026-11-04-373-custom-hybrid.md`): the free model takes the fallback where Haiku kept declining, so the fallback's value depends on the model.

## What it means for the verdict

- Under RULE.md the free model decides: the hybrid is our best custom setup on it so far, and the gap to the managed best narrows from about 13 to 21 points (metrics only) to about 9.
- Not yet a verdict: the rule compares at k = 3 with paired intervals; the k = 3 passes follow after the k = 1 lane (profile § The completion plan).

## `native-mcp` on the free model, the first 23 frozen cases (2026-11-05, 00:55Z to 01:05Z)

- The lane started `native-mcp` frozen with what was left of the day's cap (`--requests 129` at a free count of 721); Google's MCP servers spend about five or six model calls a case, so the pass stopped at the cap after 23 of 96 cases (exit 3) and the lane skipped `native-mcp` hard (free count 840 of 850).
- Those 23 cases are all right (23 of 23), but they are the set's first 23, all `covered` and `trap` questions: no `uncovered` question has run, so the figure says nothing yet against the hybrid.
- The rest of the frozen set and the hard set follow from the 2026-11-06 00:00Z reset.

## Still unknown

- `native-mcp` on the rest of the frozen set and on the hard set (from the next reset).
- The hybrid at k = 3 on the free model; whether its fallback answers are right more often than the data agents' SQL on the same `uncovered` questions.
