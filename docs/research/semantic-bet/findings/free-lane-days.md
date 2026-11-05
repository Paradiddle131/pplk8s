# The free lane, day by day: the handoff between wakes

Each wake of `probes/lanes/free_lane.sh` appends one dated block here before it ends: the next wake reads the newest block first (profile § The completion plan, 2026-11-05).
A block holds the OpenRouter free count at start and end, each pass touched (case-runs logged today, and its log's total against the set: 96 frozen, 43 hard), the pass left mid-way, the figures that moved, anomalies, and "Next:".

## 2026-11-05 (the session from 19:13Z, on the day's leftover quota)

- Free count 855 at 19:59Z (the 01:05Z lane stopped at its old cap of 850); the lane now spends up to 990 and runs every pass from the top, skipping a whole log (commit 5854fd8).
- `custom-hybrid` frozen and hard: already whole at k = 1, skipped (one frozen run still unscored from the 2026-11-05 transfer error, retried).
- The judge after the two skipped passes spent 36 requests on unclear turns already logged (855 to 891).
- `native-mcp` frozen, k = 1: 20:08Z to 20:20Z, 14 more cases (23 to 37 of 96), exit 3 at its share; free count 993, then 997 after the push; `native-mcp` hard skipped for the day.
- Moved (`measured`, results.json at d7583ac): free-model `native-mcp` frozen 94.6% [86.5, 100.0] right, 5.4% [0.0, 13.5] confident-wrong on 37 cases (`covered` 94% of 35, `trap` 88% of 8, `uncovered` 2 of 2); its first two confident-wrong answers; still mostly `covered` questions, so no read yet against the hybrid's `uncovered` 52%.
- Anomalies: none; GCP cost $0.000010 (the known Artifact Registry egress), usage check ok, before the pass.
- Not on OpenRouter: Opus as a fresh Claude Code subagent went from 20 to 50 frozen cases (74.0% right, 0.0% confident-wrong; `2026-11-04-374-cc-metricflow.md`).
- Next: the 00:07Z wake on 2026-11-06 starts the lane from the top; the first pass with work is `native-mcp` frozen from case 38 (k = 1), then `native-mcp` hard, `custom-toolbox` both sets, `baseline` (48 of 96 frozen, 0 of 43 hard), `custom-lightdash` (41 of 96 frozen, 0 of 43 hard), then the k = 3 round.
