# The free lane, day by day: the handoff between wakes

Each wake of `probes/lanes/free_lane.sh` appends one dated block here before it ends: the next wake reads the newest block first (profile § The completion plan, 2026-11-05).
A block holds the OpenRouter free count at start and end, each pass touched (case-runs logged today, and its log's total against the set: 96 frozen, 43 hard), the pass left mid-way, the figures that moved, anomalies, and "Next:".

## 2026-11-05 (the session from 19:13Z, on the day's leftover quota)

- Free count 855 at 19:59Z (the 01:05Z lane stopped at its old cap of 850); the lane now spends up to 990 and runs every pass from the top, skipping a whole log (commit 5854fd8).
- `custom-hybrid` frozen and hard: already whole at k = 1, skipped (one frozen run still unscored from the 2026-11-05 transfer error, retried).
- The rest of today's quota went where the lane reached next (`native-mcp` frozen from case 24); the end of this block is written when the lane exits.
- Not on OpenRouter: Opus as a fresh Claude Code subagent went from 20 to 50 frozen cases (74.0% right, 0.0% confident-wrong; `2026-11-04-374-cc-metricflow.md`).
- Next: the 00:07Z wake on 2026-11-06 starts the lane from the top; the first pass with work is `native-mcp` frozen (k = 1), then `native-mcp` hard, `custom-toolbox` both sets, `baseline` (48 of 96 frozen, 0 of 43 hard), `custom-lightdash` (41 of 96 frozen, 0 of 43 hard), then the k = 3 round.
