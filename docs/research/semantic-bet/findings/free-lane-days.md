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

## 2026-11-06 (the lane run by hand in the report-feedback session, after the scheduled wake failed to start)

- The scheduled task "semantic-bet free lane (daily, after the 00:00Z reset)" fired at 00:08Z and failed in 3 s: "Setup script failed" (its fresh session has no repositories, so the environment's `bash /home/user/claude-dotfiles/bin/cloud-setup.sh pplk8s` finds no clone); the session that was handling the owner's report feedback ran the lane by hand instead, exactly as the task's prompt says.
- Gates at 00:32Z: free count 0 of 1,000; `make services-up` and the agents fixture ok; GCP cost $0.000010 (the known Artifact Registry egress), usage check ok; the same after the lane at 02:38Z.
- Free count 0 at 00:35Z, 991 at 02:38Z (the lane's cap of 990, overrun by the last case's own calls); the container restarted at about 01:02Z mid-pass, and the lane was restarted at 01:05Z from its logs (no case lost: the log's last line was whole and pushed first).
- `custom-hybrid` frozen and hard: already whole at k = 1, skipped; the judge between passes spent its share on unclear turns (12 verdicts logged today).
- `native-mcp` frozen, k = 1: 59 cases today (38 to 96), log whole, 96 of 96.
- `native-mcp` hard, k = 1: 43 cases today, log whole, 43 of 43.
- `custom-toolbox` frozen, k = 1: 96 cases today, log whole, 96 of 96.
- `custom-toolbox` hard, k = 1: 43 cases today, log whole, 43 of 43.
- `baseline` frozen, k = 1: 8 cases today (49 to 56), stopped at the day's cap, 56 of 96; `baseline` hard skipped for the day (0 of 43).
- Moved (`measured`, the report rebuilt at f2ff858 from results.json written 2026-11-06T02:37Z), free model unless named:
  - `native-mcp` frozen 88.5% [82.3, 94.8] right, 6.2% [2.1, 11.5] confident-wrong; against the managed best (`native-context-bare`, 94.1%) paired by question −5.6 points [−11.8, 0.3] right and +5.2 [1.0, 10.4] confident-wrong.
  - `native-mcp` hard 93.0% [83.7, 100.0] right, 0 of 43 confident-wrong; against the managed best (94.6%) −1.6 points [−7.0, 2.3]: a tie on the hard set at k = 1.
  - `native-mcp` answers 83% of the frozen set's uncovered questions and 100% of the hard set's (19 questions), against the hybrid's 52% and 84%; it now leads the hard set's uncovered pillar.
  - `custom-toolbox` frozen 38.5% [29.2, 47.9] right, declining 49 of 96 (Haiku 43.1%, Sonnet 41.7%: the setup's reach, not the model); hard 39.5% [25.6, 53.5] right and 16.3% [7.0, 27.9] confident-wrong.
  - `baseline` frozen 67.9% [55.4, 80.4] right on 56 of 96, 10.7% confident-wrong.
- What the day says: Google's MCP servers driven by our ADK agent on the free model are, at k = 1, within a few points of the best managed agent on both sets and ahead of the MetricFlow hybrid on both, but state wrong numbers unhedged more often on the frozen set (6.2% against the hybrid's 1.0%); the generated Toolbox tools trail every other setup on every model.
- Anomalies: none (two OpenRouter transfer errors, retried by the pass; the container restart is infrastructure).
- Next: the 00:07Z wake on 2026-11-07, if its setup starts (the owner's fix: the environment's Repositories list, or a guarded setup script); otherwise a session runs `probes/lanes/free_lane.sh` by hand. The first pass with work is `baseline` frozen from case 57 (k = 1), then `baseline` hard (0 of 43), `custom-lightdash` frozen from case 42 and hard (0 of 43; the 15 GB image, last), then the k = 3 round from `custom-hybrid` frozen.

## 2026-11-06 (the epic #375 session: hard-v2 frozen and carried, the data agents on it; no OpenRouter left)

- Free count 991 of 1,000 at 09:43Z (spent by the lane run by hand at 02:38Z): no free-model pass today.
- The lane's order changed (e28a069, #379): v1's k = 1 round (left: `baseline` frozen from case 57, `baseline` hard 0 of 43, `custom-lightdash` both sets), then `bet_carry` and the hard set v2 (`hard-v2`, 58 cases, RULE.md § Set versions) at k = 1 and k = 3 for `custom-hybrid`, `custom-metricflow`, `native-mcp` and `baseline`, then the frozen set's k = 3 round; v1-hard's k = 3 round is dropped.
- `hard-v2` logs (`eval-hard-v2-*.jsonl`) hold v1's runs of its 43 unchanged cases, carried with `carried_from` and a hash (3,222 runs, 84 verdicts); free-model logs on `hard-v2`: `custom-metricflow` 43 cases at k = 3, `custom-hybrid` and `native-mcp` 43 at k = 1, `baseline` none; none of the 15 new cases yet.
- The gcp lane, by hand (`probes/lanes/gcp_pass.sh <mode> hard-v2 <arm> <k>`, 09:47Z to 10:56Z): `native-context-bare` (thinking), `native-bare`, `native-context` and `native-kc-max` on the 15 new cases, k = 1 then k = 3: 180 of 180 runs right; GCP cost $0.000010 (the known egress) and the usage check ok at each of the 16 gates.
- Moved (`measured`, results.json at 10:56Z): every data agent is right on every run of `hard-v2`'s new cases, the bare floor included; so on its new cases the managed best is not off the ceiling, and the floor is not below it (RULE.md § Set versions, criteria 2 and 4, for #380 once the free-model arms are whole).
- Anomalies: none.
- Next: the 00:07Z wake on 2026-11-07 (if its setup starts; else a session runs `probes/lanes/free_lane.sh` by hand): `baseline` frozen from case 57, `baseline` hard, `custom-lightdash`, then the carry and `hard-v2` k = 1 (`custom-hybrid` 15 new cases, `custom-metricflow` 15, `native-mcp` 15, `baseline` 58).
  `hard-v2` at k = 3 then asks runs 2 and 3 of every case an arm ran only once on v1 (`custom-hybrid`, `native-mcp`, `baseline`: 43 × 2 each) besides the new cases' (15 × 2), about 440 case-runs, more than the plan's estimate of about 2,400 requests: about four daily quotas.

## 2026-11-06, later (#382: the audit, the retirements and the scorer fix)

- 23 defective cases retired and 122 misleading runs redacted (`redacted.jsonl`, RULE.md § Retiring a defective case); the bet's scorer fixed and every log rescored on read from `expected.json`; the report reads only `scored-runs.jsonl` and `results.json` (`findings/2026-11-06-382-defect-audit.md`).
- Sets as scored: frozen 76 cases, hard 41, hard-v2 55 (each log's totals are now against these).
- GCP: the data agents' 4 redacted runs rerun (native-governed 2, native-kc 1, native-context-bare thinking 1), $0.000010 at each gate.
- Next: the 00:07Z lane on 2026-11-07 starts with `backlog`: the judge on about 265 unclear turns (frozen, then hard, about 530 requests), the carry, and a push; then `baseline` frozen (now against 76 cases, its 3 redacted free-model runs included), `baseline` hard, `custom-lightdash`, then `hard-v2` k = 1.

## 2026-11-06, 2026-11-06T15:53Z (the scheduled free-lane wake: quota already spent)

- Free count 991 of 1,000 at the start and at the end (read from `/api/v1/key`): the 00:00Z quota was spent by the by-hand lane at 02:38Z, so no free-model pass ran and no gate beyond that was needed.
- Passes touched: none; no log changed, so no new right or confident-wrong figure moved and the report was not rebuilt.
- Anomalies: none.
- The #335 watch line for the later read is in `watch.md` (catalog MCP `compile_query` still 404; PyPI versions unchanged).
- Next: the 00:07Z wake on 2026-11-07 starts `free_lane.sh` with `backlog` (the judge on about 265 unclear turns, the carry), then `baseline` frozen (against 76 cases), `baseline` hard, `custom-lightdash`, then `hard-v2` at k = 1.

## 2026-11-06, 2026-11-06T15:58Z (the epic #375 session after the re-run wake: no second lane)

- Free count 991 of 1,000 at the start (read from `/api/v1/key`), and the train's head (527861e, 15:53:57Z) was 4 minutes old from the re-run scheduled wake: by the lane guard, no second lane, no model call, no gate needed.
- The scheduled task's re-run (15:52:59Z) started and finished as `SUCCEEDED` with the two repositories added, so the setup failure of the night's firing should not recur; its next firing is 2026-11-07T00:07Z.
- Passes touched: none; no log changed and the report was not rebuilt.
- #379 stays open (the free-model arms are not whole on `hard-v2` at k = 3), so #380 does not start; #381 waits for the owner's go on #380.
- Anomalies: none.
- Next: the 00:07Z wake on 2026-11-07 runs `free_lane.sh` from `backlog` (the judge on about 265 unclear turns, about 530 requests), then `baseline` frozen (against 76 cases), `baseline` hard, `custom-lightdash`, then `bet_carry` and `hard-v2` at k = 1; #379 needs about four daily quotas in all.
