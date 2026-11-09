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

## 2026-11-06, 2026-11-06T16:37Z (the owner's go for the subagent pass and #380's script; no OpenRouter)

- Free count 991 of 1,000 all session: no free-model pass ran; the subagent lane and one gcp run used no OpenRouter.
- `cc-metricflow` (Claude Code subagents) on `hard-v2`'s 14 new cases, scored: fresh Haiku and Sonnet k = 3 (42 runs each), fresh Opus k = 1 (14), batched Haiku, Sonnet and Opus k = 1 (14 each); each setup's `hard-v2` log is now 55 of 55 cases (#374's finding).
- The managed best's one missing `hard-v2` run (`native-context-bare` thinking, `hv2_avg_daily_revenue_fiscal_quarter` run 3) filled by `gcp_pass.sh`: right; `gcp-cost-check` /bin/bash.000010 and `gcp-usage-check` ok before and after.
- `probes/380_compare.py` scores RULE.md's four `hard-v2` criteria from the scored data; its provisional readout is on #380: criterion 1 holds, criterion 2 splits by reading (83.3% on the 6 new `uncovered`, 92.3% on the 13 new `composable` or `uncovered`), criterion 4 fails (+0.0 points), criterion 3 waits for `custom-metricflow`'s 13 new cases.
- The report rebuilt (`results.json` 16:35Z) and republished (artifact version 20; #336's artifact 4 read back, same SHA-256).
- Anomalies: none.
- Next: the 00:07Z wake on 2026-11-07 runs `free_lane.sh` from `backlog` (it now also judges the subagents' hedged confident-wrong turns on `hard-v2`), then `baseline` frozen (76 cases), `baseline` hard, `custom-lightdash`, then `bet_carry` and `hard-v2` at k = 1; when #379 closes, `380_compare.py --whole` writes #380's numbers.

## 2026-11-06, 2026-11-06T18:10Z (session end: the fair-harness plan, four small fixes merged)

- No free-model pass (991 of 1,000 all session); the nightly 00:07Z lane is unchanged and still starts with `backlog`.
- Merged: #385 (#370 and the cost-check half of #369) and #386 (#292) into `main`; the train took `main` back, plus #369's usage-check half and #322 (labels `in-train`); the train contains `main`.
- The owner's decisions on the Claude Code setups are in the profile (§ The completion plan): no more Agent-tool eval runs; the strict headless runner (#387) and the parity audit (#388) come before any new Claude Code number; the batched and shell-tool `cc-metricflow` rows stay until the strict rows replace them.
- Report work queued: #389 (tooltip jump, approved design: a link line in the pinned tooltip with a back link at the target), #390 (three parallel Opus designs for a question-set section, one with the full searchable question list).
- Anomalies: none; GCP stayed at $0.000010 and the usage check ok at every gate.
- Next: a session builds #388's parity matrix and #387's runner (subscription, no OpenRouter), then #389 and #390; the free lane carries #379 nightly; #380 waits for #379.

## 2026-11-06, 2026-11-06T20:03Z (session end: #388 and #387 done, #389 built, #390 designs and the owner's review)

- No free-model pass (991 of 1,000 all session, read from `/api/v1/key`); the nightly 00:07Z lane is unchanged and still starts with `backlog`.
- #388: every setup's tools and context verified from code, logs and BigQuery's job history (`findings/2026-11-06-388-setup-parity.md`); `semantic_agent.bet_tools` checks every log (0 runs outside their tools) and both runners refuse such runs; RULE.md names `cc-metricflow` and `cc-native-mcp`.
- #387: the strict headless runner (`probes/387_cc_strict.py`, `probes/387_mcp_guard.py`); 2,164 strict runs, Haiku and Sonnet at k = 3 on every set for both setups, Opus 50 a setup on hard-v2; 121 mis-scored runs redacted and rescored after a fix; the report shows the strict rows in place of the subagent rows (`findings/2026-11-06-387-cc-strict.md`).
- #389: the pinned-tooltip jump, published; #390: three designs posted; the owner picked C and gave a full review, filed as epic #399 (#393 to #398, #390), with the reader rule in the profile and #336's brief.
- Report: page version 24; #336's artifact 4 read back with the same SHA-256.
- GCP: $0.000010 and the usage check ok at every gate; BigQuery at 191 GiB of the free 1 TiB this month after about 18 GiB of strict `cc-native-mcp` runs.
- Anomalies: none. Filed: #392 (the `native-mcp` guard drops BigQuery's error text).
- Nothing left running: every strict lane finished and is scored; the MCP servers are stopped.
- Next: epic #399 in its order: #393 (reader rule on the page), #394 (retired questions, the owner's decision), #395 (term tooltips), #396 (three tab designs); the free lane carries #379 nightly; #380 waits for #379.

## 2026-11-06, 2026-11-06T21:32Z (session end: epic #399's first four items, the owner's figure fixes, #400 filed)

- No free-model pass (991 of 1,000 at the start and the end, read from `/api/v1/key`); the nightly 00:07Z lane is unchanged. No GCP and no Claude API work.
- The owner's figure fixes: Figures 2 to 5 dim by one source at a time (the glider off home, else a clicked lock held until its pin closes, else hover); group legend entries and Figure 5's family titles lock by click, Enter or Space; Figure 1's column heads stay on screen (a sticky copy, which `tools/clipcheck.js` reads as a mirror).
- #393: no process metadata on the page or in its data; the reader rule is in `report/NOTES.md`, the profile, every brief under `report/variants/` and #336's brief artifact; the setup map and explorer describe the Claude Code setups as headless with only their tools, and the explorer shows `cc-native-mcp`.
- #394: the owner's decision ("Remove retired questions entirely ... remove cleanly. no clutter") is in RULE.md § Changes since freezing; nothing of a retired question is left on the page or in its data.
- #395: `TERMS` covers every group, kind, rubric kind, family and role; `tests/test_report_build.py` fails on a missing one or on a process word on the built page (6 pass).
- #396: three designs published and posted (A tab strip, B contents rail, C overview and chapters); recommended A; waiting for the owner's pick.
- #400 (new): the MetricFlow setups' score rewards breaking their no-arithmetic instruction (Haiku 64%, Sonnet 52%, Opus 42% on the extended hard set; through the metrics only 33%, 29%, 36%; the same inversion in the ADK runner on the frozen set); three options, A recommended; the owner's pick.
- Report: page version 27; #336's artifact 4 read back with the same SHA-256 (20c6870a…).
- claude-dotfiles PR #47: the generic reader rule in `cloud/CLAUDE.md`.
- Anomalies: none. Nothing left running.
- Next: #396 (the owner's pick), then #390 built into it; #400 (the owner's pick); the free lane carries #379 nightly; #380 waits for #379.

## 2026-11-06, 2026-11-06T23:04Z (session end, near the usage limit: #400 option A run, report revision 3 built)

- Free count 991 of 1,000 (no free-model pass this session); tonight's 00:07Z lane now also asks `custom-metricflow-compute` (hard-v2, then frozen) after `custom-metricflow`'s hard-v2 pass in each `hard_v2` round.
- #400: the owner chose A; `custom-metricflow-compute` and `cc-metricflow-compute` joined (RULE.md 2026-11-06T21:57Z); strict Claude Code passes done: Haiku and Sonnet k = 3 on frozen (86%, 86%), hard (80%, 76%), hard-v2 (75%, 72%), Opus 50 on hard-v2 (74%); the inversion of `cc-metricflow` (64%, 52%, 42%) is gone.
- #396: the owner picked A; built into the page with titles only. #401 (filed): grouped glossary table, structured tooltips, impeccable detector pass: done, waiting for the owner's look.
- Report: page version 28; #336's artifact 4 read back with the same SHA-256 (28ffaa4b…).
- A container restart at about 22:45Z stopped the metrics MCP server and the lane mid-pass; the runner's init check refused the runs without tools, and the pass resumed from its answers file; nothing was mis-scored.
- Nothing left running; the Compose services were up when the session ended (they do not survive a new session).
- Next: #400's open question (should the headline "MetricFlow on the free model" read `custom-metricflow-compute` once the free lane has run it); then #390 (the question section, option C, inside the "Question sets" tab), #397, #398; the free lane carries #379 and the new setup nightly.

## 2026-11-07, 2026-11-07T01:45Z (the 00:07Z wake; the lane stopped at an anomaly: `custom-lightdash` hard canary)

- Free count 0 at the start, 544 of 1,000 at the end (read from `/api/v1/key`); 456 requests went unspent because the lane stopped.
- Anomaly, first: `custom-lightdash` hard k = 1 missed its canary twice (exit 2, `hard_top_channel_bookings`): its answer was "campaign 1 brought the most bookings, 31; the bookings explore groups by campaign_id, channel is not a dimension on slv_bookings".
  That reads as the arm's tool surface lacking a channel dimension, not a broken warehouse, agent or model (the frozen pass ran whole minutes earlier); suspected cause, not verified.
  `--no-canary` was not used.
  The lane never reached `bet_carry`, the `hard-v2` passes, `custom-metricflow-compute` or any k = 3 pass.
- Gates at the start: free count reset, `services-up`, the agent fixture, `gcp-cost-check` exit 0 ($0.000010, the same Artifact Registry SKU) and `gcp-usage-check` ok; the cost check after the lane was not re-run (the lane's own gate passed before `native-mcp`, no GCP work was done).
- Passes (Nemotron free; cases of the set as scored, frozen 76, hard 41, hard-v2 55):

| Pass | Logged today | Log's total now |
|---|---|---|
| backlog judge | the backlog after the #382 scorer fix | |
| `custom-hybrid` frozen / hard k = 1 | none new (the first call hit an OpenRouter transfer error, exit 3, then the rest of the lane went on; the log was whole) | frozen 76 of 76, hard 41 of 41 |
| `native-mcp` frozen / hard k = 1 | none new (log whole) | 76 of 76, 41 of 41 |
| `custom-toolbox` frozen / hard k = 1 | 3 calls (log whole) | 76 of 76, 41 of 41 |
| `baseline` frozen k = 1 | about 125 calls, the rest of the set | 76 of 76 |
| `baseline` hard k = 1 | about 196 calls | 41 of 41 |
| `custom-lightdash` frozen k = 1 | about 80 calls (the Lightdash image pulled and started) | 76 of 76 |
| `custom-lightdash` hard k = 1 | none: stopped at the canary | not started |

- Mid-way: `custom-lightdash` hard k = 1 (0 of 41); everything after it in the lane order is untouched today.
- Figures that moved (Nemotron free, k = 1, right / confident-wrong): frozen `baseline` 59.2% / 7.9% (was 49 of 76 questions); frozen `custom-lightdash` 59.2% / 7.9% (was 38 of 76); hard `baseline` 48.8% / 19.5%.
  Unchanged: frozen `custom-metricflow` 89.5% / 0.0%, `custom-hybrid` 89.5% / 0.0%, `native-mcp` 89.5% / 3.9%, `custom-toolbox` 43.4% / 5.3%; hard `native-mcp` 90.2% / 0.0%, `custom-hybrid` 82.9% / 0.0%, `custom-toolbox` 39.0% / 14.6%.
- What the numbers say: with the whole frozen and hard sets at k = 1, the plain text-to-SQL `baseline` and Lightdash's metric API land well under the managed best (`native-mcp`) and the hybrid on the free model: 59% against 89.5% on frozen, 49% against 83% to 90% on hard, and `baseline` carries the most confident-wrong answers on hard (19.5%, against 0.0% for `native-mcp` and `custom-hybrid`).
  Correction, 2026-11-09 (#451): `native-mcp` is rung 3 (our agent on Google's tools), not the managed best; RULE.md's managed best is the best rung 1-2 data agent, `results.json` `managed_best` (`native-context-bare` on the hard sets).
  One run a question, so the intervals still overlap for the close pairs.
- Report: page version 32; #336's artifact 4 read back with the same SHA-256 after each rebuild.
- Next: decide the canary for `custom-lightdash` hard (use a case the arm's explore can answer, or skip that pass; the owner's or the next session's call, never `--no-canary`), then start `free_lane.sh` again: it resumes at `bet_carry` and the `hard-v2` k = 1 round (`custom-hybrid`, `custom-metricflow`, `custom-metricflow-compute`, `native-mcp`, `baseline`), then k = 3.

## 2026-11-07, 2026-11-07T12:05Z (a session: the free lane by hand, MetricFlow with arithmetic on the free model, report revisions 3 and 4)

- Free count 544 at the start (left from the 00:07Z wake), 961 of 1,000 at the end; the lane ran by hand from 08:40Z and was stopped at 10:40Z by the session's two-hour limit on a background job, near the day's cap.
- Lane: `custom-lightdash` takes the frozen set's canary before a hard pass (its explores have no channel dimension; the hard case is still asked and scored, `bet_eval.CANARY_SET`); its hard k = 1 pass then ran whole (41 of 41).
- `custom-metricflow-compute` on the free model, extended hard set k = 1: 74.5% right, 5.5% confident-wrong, 55 of 55 (`custom-metricflow` 68.5% / 4.8%, `custom-hybrid` 74.5% / 3.6%); its frozen pass has not started.
- The headline "MetricFlow on the free model" reads `custom-metricflow-compute` once its free runs cover a set (owner's "yes" on #400; RULE.md 2026-11-07T08:50Z).
- `native-context-python` (Python analysis on) ran the extended hard and frozen sets at k = 1 and never took a Python step; dropped from the page by the owner; its runs stay in the logs (`findings/2026-11-07-python-analysis.md`).
- Report: revision 3's question section (#390), question browser A (#397), then revision 4 (#399): one decision map with a set switch, sorting, filters and four scores (accuracy, coverage, selective accuracy, pass^3); Every run's question highlight with its strip; draggable pinned tooltips; structured glossary entries; page version 36; #336's artifact 4 read back with the same SHA-256.
- Anomalies: none; GCP cost $0.000010 (the known Artifact Registry line) at every check.
- Nothing left running.
- Next: tonight's 00:07Z wake resumes at `custom-metricflow-compute` frozen k = 1, then `native-mcp` and `baseline` on hard-v2, then k = 3; after the lane, #380.

## 2026-11-07, 2026-11-07T12:48Z (a session: report housekeeping, the newcomer read, #384's fix; no OpenRouter)

- Free count 961 of 1,000 at the start (read from `/api/v1/key`), unchanged at the end: no lane ran, none was running; tonight's 00:07Z wake resumes the lane.
- Extended hard set (hard-v2), free model: `custom-hybrid`, `custom-metricflow-compute` 55 of 55 at k = 1, `custom-metricflow` 137 of 165 runs toward k = 3; `native-mcp` and `baseline` 41 of 55 at k = 1 (the carried cases only); no k = 3 pass whole yet, so #379 stays with the lane and #380 waits.
  Data agents on the same set: `native-bare`, `native-context`, `native-kc-max` and `native-context-bare` (default model) whole at k = 3.
- Closed, each checked against its "Done when": #390, #393, #394, #395, #396, #397, #398, #400, #401 and the epic #399.
- #395's newcomer read: a fresh reader over every tab's text; the undefined words got glossary terms and tooltips (tools and products, models, harness, rung, points, tolerance, hedge, blind judge; every model name in the decision map); "Abstract." reads "In short."; `custom-metricflow` and `cc-metricflow` now say that a model which obeys their no-arithmetic rule scores lower (#400).
  The rest of that read (captions against tables, code names in prose, the partial leader) is #409; its first item is diagnosed there: Figure 1 compares with the best Google agent per group (87%), Figure 4 with the managed best (80%).
- Report: page version 39; #336's artifact 4 PATCHed and read back with the same SHA-256 (09c407aa…); `test_report_build.py` 23 passed; `clipcheck.js --quick` 0 findings.
- #384: PR #410 onto the train (the warehouse's reason reaches the model); held for merge between passes, after the MetricFlow arms' extended-hard-set k = 3, so no pass mixes two error texts.
- #392 and #383: not changed; each changes what an open pass measures (the `native-mcp` guard; the fixture under the frozen set's `candidates_in_interview_as_of`); decision packets on each, lines in Map #324's digest.
- Anomalies: none; no GCP work, so no cost check was run.
- Nothing left running.
- Next: tonight's 00:07Z wake runs the lane (`native-mcp` and `baseline` hard-v2 k = 1, then the k = 3 round); after the MetricFlow arms' hard-v2 k = 3, merge #410; once #379's arms are whole at k = 3, #380.
- Addendum, 2026-11-07T13:03Z: the owner answered all three questions ("#392 and #383 as recommended; #409 use managed best everywhere").
  #392's fix is PR #411, with its RULE.md entry; like #410, it merges once `native-mcp`'s extended-hard-set k = 3 pass is whole.
  #383 waits for the frozen k = 3 round.
  #409's Figure 1 now compares with the managed best (page version 40; #336's artifact 4 has the same SHA-256); #409's other items remain.
- Addendum, 2026-11-07T13:22Z: #409 closed (page version 41).
  Figures 3, 5 and 6 name their set; the summary says what each count covers; the partial leader is tagged "so far"; setup ids stay as names, by design.
  Next is unchanged: tonight's 00:07Z wake, then the merges of #410 and #411, then #380.

## 2026-11-08, 2026-11-08T12:10Z (the daily wake: the free lane from 09:25Z)

- Free count 0 at the start, 963 of 1,000 at the end (read from `/api/v1/key`); the lane stopped itself at its 990 cap (`skip custom-metricflow hard-v2 k=3: free count 963 of 990`).
- Gates at the start: free count reset, `services-up`, the agent fixture, `gcp-cost-check` exit 0 ($0.000010, the same Artifact Registry SKU, as on 2026-11-07) and `gcp-usage-check` ok; no GCP work in the lane, and the cost check after it again read $0.000010.
- Anomalies: none (exit 3 on a `hard-v2` pass is "log not whole for the set as scored", not a gate; `custom-hybrid` and `custom-metricflow` `hard-v2` k = 1 and `custom-metricflow-compute` `hard-v2` k = 1 ended 3 with no request spent, their logs already held 55 of 55).
  One OpenRouter transfer error (`TransferEncodingError`) on a `custom-hybrid` turn, retried by the lane; recorded as "No answer" in the log as before.
- Passes (Nemotron free; cases of the set as scored: frozen 76, hard 41, hard-v2 55, read from `results.json`):

| Pass | Logged today | Log's total now |
|---|---|---|
| backlog judge | the backlog | |
| v1 k = 1 round: `custom-hybrid`, `native-mcp`, `custom-toolbox`, `baseline`, `custom-lightdash` (frozen and hard) | none (all whole; the Lightdash image started) | 76 and 41 of each |
| `custom-metricflow-compute` frozen k = 1 | 281 calls | 76 of 76 |
| `native-mcp` hard-v2 k = 1 | about 170 calls | 55 of 55 |
| `baseline` hard-v2 k = 1 | about 170 calls | 55 of 55 |
| `custom-hybrid` hard-v2 k = 3 | about 500 calls | 165 of 165 runs (55 cases x 3) |

- Mid-way: nothing; the next pass in order, `custom-metricflow` hard-v2 k = 3 (137 of 165 runs), was skipped on the cap.
- Figures that moved (Nemotron free, right / confident-wrong): frozen `custom-metricflow-compute` 89.5% / 0.0% (k = 1); hard-v2 `native-mcp` 92.7% / 0.0%, `baseline` 45.5% / 23.6%, `custom-hybrid` 76.4% / 4.8% at k = 3 (was 74.5% / 3.6% at k = 1).
  Unchanged: hard-v2 `custom-metricflow` 68.5% / 4.8%, `custom-metricflow-compute` 74.5% / 5.5%; frozen and hard v1 rows as on 2026-11-07.
- What the numbers say: on the extended hard set `native-mcp` (the managed best) leads at 92.7% with no confident-wrong answer; the hybrid's k = 3 reading (76.4%) and the MetricFlow arms (68.5% to 74.5%) sit 16 to 24 points under it, while plain text-to-SQL `baseline` is worst with the most confident-wrong answers (23.6%).
  Correction, 2026-11-09 (#451): `native-mcp` is rung 3 (our agent on Google's tools), not the managed best; RULE.md's managed best is the best rung 1-2 data agent, `results.json` `managed_best` (`native-context-bare` on the hard sets).
  The hybrid's k = 3 move (74.5% to 76.4%) is inside the interval; MetricFlow with arithmetic matches the hybrid on this set, as on 2026-11-07.
- Report: rebuilt after the judge backlog, `custom-metricflow-compute` frozen, the hard-v2 k = 1 round and the final pass (build with `python3.12`: the session's `python3` is 3.11 and `build.py` needs 3.12 f-strings); claude.ai artifact published, #336's artifact 4 read back with the same SHA-256 after each rebuild.
- Next: tomorrow's wake starts with `custom-metricflow` hard-v2 k = 3 (28 runs left), then `custom-metricflow-compute` hard-v2 k = 3, `native-mcp` and `baseline` hard-v2 k = 3, then the frozen set's k = 3 round; #380 and the merges of #410 and #411 wait on those.

## 2026-11-09, 2026-11-09T03:45Z (the daily wake: the free lane from 00:12Z, stopped by the session's 2-hour background limit)

- Free count 0 at the start, 595 of 1,000 at the end (read from `/api/v1/key`); 405 of the day's requests unspent.
- Gates at the start and again after a container restart at about 01:30Z: free count reset, `services-up`, the agent fixture, `gcp-cost-check` exit 0 ($0.000010, the same Artifact Registry SKU as on 2026-11-08) and `gcp-usage-check` ok; no GCP work in the lane.
- Anomalies: none from the lane (no exit 1 or 2; exit 3 on the hard-v2 k = 3 passes is "log not whole for the set as scored" at the pass's start, and each log is whole now).
  Two interruptions that cost requests but no data: the container restarted at about 01:30Z mid `custom-metricflow` hard-v2 k = 3 (its 15 whole lines pushed, the lane restarted and spent about an hour re-skipping the whole passes and re-pulling the Lightdash image); then the session's runner stopped the restarted lane at its 2-hour background limit at 03:41Z, mid `custom-metricflow-compute` frozen k = 3, and a job already given the longest limit is not restarted.
  Correction, 2026-11-09 (#451): the lane stopped at 03:34Z, when its 2-hour background limit ran out; 03:41Z is when the stop notice arrived.
  A wake's lane therefore gets at most 2 hours from its start, and the v1 round of whole passes takes about 45 minutes of that before any request is spent.
- Passes (Nemotron free; cases of the set as scored: frozen 76, hard 41, hard-v2 55, read from `results.json`):

| Pass | Logged today | Log's total now |
|---|---|---|
| v1 k = 1 round and hard-v2 k = 1 round (every arm) | none (all whole; the Lightdash image started) | as on 2026-11-08 |
| `custom-hybrid` hard-v2 k = 3 | none (whole) | 165 of 165 runs |
| `custom-metricflow` hard-v2 k = 3 | 28 runs | 165 of 165 runs (55 cases x 3) |
| `custom-metricflow-compute` hard-v2 k = 3 | 110 runs | 165 of 165 runs |
| `custom-metricflow-compute` frozen k = 3 | 18 runs | 94 of 228 runs (76 cases x 3) |

- Mid-way: `custom-metricflow-compute` frozen k = 3, stopped at 94 of 228 runs (run 2 under way); its partial runs are in `eval-local.jsonl` and `results.json` still shows its k = 1 reading.
- Figures that moved (Nemotron free, right / confident-wrong): hard-v2 `custom-metricflow` 66.7% / 6.1% at k = 3 (was 68.5% / 4.8% with 137 of 165 runs); hard-v2 `custom-metricflow-compute` 76.4% / 5.5% at k = 3 (was 74.5% / 5.5% at k = 1).
  Unchanged: hard-v2 `native-mcp` 92.7% / 0.0% and `baseline` 45.5% / 23.6% (k = 1), `custom-hybrid` 76.4% / 4.8% (k = 3); frozen and hard v1 rows as on 2026-11-08.
- What the numbers say: on the extended hard set the managed best, `native-mcp`, still leads at 92.7% with no confident-wrong answer (k = 1 so far); MetricFlow with arithmetic now ties the hybrid exactly at k = 3 (76.4%), both about 16 points under it, while plain MetricFlow's k = 3 reading slipped to 66.7% with more confident-wrong answers (6.1%), so arithmetic is worth about 10 points on this set.
  Correction, 2026-11-09 (#451): `native-mcp` is rung 3 (our agent on Google's tools), not the managed best; RULE.md's managed best is the best rung 1-2 data agent, `results.json` `managed_best` (`native-context-bare` on the hard sets).
  `native-mcp` and `baseline` at k = 3 on hard-v2 decide whether the 16-point gap holds.
- Report: rebuilt and republished after the judge backlog, `custom-hybrid` frozen, `custom-metricflow` hard-v2 k = 3 and `custom-metricflow-compute` hard-v2 k = 3 (page versions 47 to 50, built with `python3.12`); #336's artifact 4 read back with the same SHA-256 each time (the PATCH answer now carries `body` at its top level, not under `.artifact`); the Approaches page's build was unchanged by these passes and was not republished.
- Next: tomorrow's wake starts with `custom-metricflow-compute` frozen k = 3 (134 runs left), then `native-mcp` and `baseline` hard-v2 k = 3, then the rest of the frozen set's k = 3 round; with the 2-hour limit, a wake that restarts the lane after the limit would finish the day's quota (owner's call).
