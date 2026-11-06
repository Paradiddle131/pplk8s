# Autopilot profile — the semantic agent bet (a parallel track)

A second profile beside [`autopilot.md`](autopilot.md), for the research track [Map #324](../../../../issues/324) on branch `claude/semantic-bet` (`semantic/PLAN.md` SL-25).
Wakes follow the `dotfiles:autopilot` skill (if missing, read `/home/user/claude-dotfiles/cloud/skills/autopilot/SKILL.md`) with the slots below; `autopilot.md`'s Gates, Never and Known conditions still apply wherever this file says nothing.
The routine prompt: "Follow `docs/agents/autopilot-semantic-bet.md` on branch `claude/semantic-bet` in pplk8s and do one wake."
Standing permission (owner, 2026-11-02): everything `autopilot.md` allows, plus filing new issues under Map #324 when its queue runs dry, and live steps on the lab project inside the $0.00 rule below.

## Why this track exists

- The owner is reconsidering the whole direction: Knowledge Catalog now ingests dbt MetricFlow (GA), so "a GCP-native data agent lacks a semantic layer" may no longer hold, and must be seen in action.
- Its one output is a final report with a verdict on what is worth building from here, possibly a new repo that fills only the true gaps: [`docs/research/semantic-bet/README.md`](../research/semantic-bet/README.md) holds the questions, the arms and where findings go.

## Delivery

`train claude/semantic-bet` with `AUTOPILOT_BASE=main`: `export AUTOPILOT_TRAIN=claude/semantic-bet AUTOPILOT_BASE=main` before the scripts.
The train is stacked on PR #310 (`claude/bold-ritchie-5qpzgk`, the data-agent tooling): while #310 is open, after `train_sync.sh` also `git merge --no-edit origin/claude/bold-ritchie-5qpzgk` and push; a conflict there is an upkeep-only wake, commented on the train PR.
A conflict between #310 and `main` (owner, 2026-11-03: "no need to ask while I'm away"): merge `origin/main` into `claude/bold-ritchie-5qpzgk` with the resolution the train already holds, run `make lint` and `make agent-test`, push that branch, and say so in the train's handoff; the routine prompt's "push only `claude/semantic-bet`" is stricter until the owner changes it, so until then a wake files the reconcile as the digest's top line instead.
The train PR targets `main`; its first line says #310 merges first.

## Digest

Map #324's body: the steering lines on top (`Mode: full | offline | paused`, `Owner lane: …`), then the open owner questions, one line each; #43 is the main track's digest, not this one.
`Mode: full` lets a wake do the live steps below; `offline` keeps it to the Compose stand-ins and the emulator.

## Queue

1. Map #324's `autopilot-ready` sub-issues, in the order its body's table gives, each pickable only when its `Blocked by` are closed or `in-train`.
2. Refill (owner, 2026-11-02): when nothing in the map is pickable, file up to three new sub-issues of #324 that answer an open question in the README's register or sharpen the verdict (labels `semantic-bet`, `semantic`, `autopilot-ready`; the `issue` skill's shape), then pick one in the same wake.
   New scope outside the register is filed `needs-user` instead.
3. Nothing pickable or worth filing, and the report landed: only the watch (#335, at most once a day), then end.

The main track's queue never picks a `semantic-bet` issue, and this track never picks one of the main track's.

## Live steps (the lab project)

- pplk8s's $0.00 rule holds on this track (owner, 2026-11-02): `make gcp-cost-check` and `make gcp-usage-check` before and after every live step; exit 1 (a cost) or 3 (not provable yet) ends the wake's GCP work, first in its handoff.
- Data agents are free until 2026-12-31: create one agent per arm, named `bet-<arm>`; the credential can create and chat, not update or delete others' agents.
- The $0 guard refuses `gcloud dataplex` writes and other paid-product writes: treat it as the answer, never route around it; the step becomes a needs-user packet holding the exact Cloud Shell command (below).
- BigQuery: dry-run first, `maximum_bytes_billed` on every job, new datasets named `bet_<issue-topic>` in the `US` multi-region (the semantic layer's region), each listed in its finding.
- Don't edit `platform/gcp/**` or the Makefile's `gcp-*` targets (#43's owner lane): probes live in `docs/research/semantic-bet/probes/`, and grants the owner made by hand are listed in the findings, so drift in `make gcp-plan` is expected and named.

## Models

- OpenRouter free models only (1,000 requests a day, owner 2026-11-02), shared with other scheduled runs: on a spent quota, write what was measured and stop model work for the wake.
- Claude through the Anthropic API, for eval arms only, within the owner's $100 budget once the owner provides the key (owner, 2026-11-02; the cloud rules' OpenRouter line is unchanged): a wake that needs it and finds no key adds one digest line and continues other work; every run logs its spend in its finding.
- Looker is out of scope, lab included (owner, 2026-11-02: not available at work).

## The owner on the phone

The owner can rarely intervene: ask only to get truly unblocked, once per blocker.
- A needs-user packet on the issue (the skill's decision packet); a console step is one paste-able Cloud Shell block, saying what it changes and how to undo it.
- One line in Map #324's digest, most blocking first.
- The wake's final message starts with `OWNER NEEDED: <one line>` (the routine pushes it to the owner's phone); call `PushNotification` too when the tool exists.
Then keep working on whatever the blocker doesn't touch.

## Recording

- Each issue's evidence is one file, `docs/research/semantic-bet/findings/<YYYY-MM-DD>-<issue>-<slug>.md`: the question, what was run (commands, calls, model, dates), what was observed (raw excerpts), what it means for the verdict, what stays unknown, sources.
- The register in `docs/research/semantic-bet/README.md`: change only your rows (status and finding link).
- Mark each fact `measured` (with its run) or `stated` (with its URL and the date read).
- A case that looks defective (owner, 2026-11-06): write the evidence on its own issue and propose retiring it under RULE.md § Retiring a defective case; it leaves the scores only once the owner confirms, and never because of which arm passes or fails it.
- A `ledger.d/` fragment per finished issue; lessons for work go to `semantic/PLAN.md` § 6 only with the final report.

## Gates

- Docs only: `git diff --check`.
- Probes: `uvx ruff@0.17.0 check docs/research/semantic-bet/probes && uvx ruff@0.17.0 format --check docs/research/semantic-bet/probes`.
- `services/semantic-agent/**` changed: `make agent-test`; `dbt/**` changed: dbt from the host as `autopilot.md` § Gates says; any code: `make lint`.
- `make check` once on the train's head before the final report lands.

## The final report

- The brief is #336's artifact "Brief - the report the owner asked for" (`gh api repos/<o>/<r>/issues/336/artifacts`): the owner's questions, form and data rules; a new owner hint or a hint from the work is added to it with a `PATCH`, never as a new artifact or a comment; the report reads its numbers only from `results.json` (written with every `eval.md`).
- [#336](../../../../issues/336): `docs/research/semantic-bet/REPORT.md` and an HTML version (an artifact on Map #324, and a published page when the Artifact tool exists), answering every register question with evidence or "still unknown", with the verdict.
- When it lands, the digest says "Report ready" and the wake's final message starts with `OWNER NEEDED: report ready; read it and turn the routine off`.

## The completion plan (owner, 2026-11-04)

The owner, in a session, 2026-11-04: "Eventually, I would like the report to include everything that we have planned. So I don't mind spending a few days to complete the open router test results ... as well as the Claude models through Anthropic API ... If there is an anomaly, we should stop. Otherwise, we can just test them anytime"; and "you can merge PRs for the sake of completeness under this semantic-bet epic".
Each wake runs every pass below whose resource is free, side by side (one background job per lane, each under its lock), and pushes the train after every pass; the logs resume, so a cut pass costs nothing but its last case-run.

| Lane | Resource | Passes, in order (each on the frozen set, then the hard set, k = 3 unless named) |
|---|---|---|
| free | OpenRouter, 1,000 a day from 00:00Z, `openrouter.lock` | `custom-hybrid` (#373), `native-mcp` and `custom-toolbox` at k = 1, then to k = 3; `custom-metricflow`'s frozen runs 2 and 3; `custom-lightdash` (pull the Lightdash image first, #363); `baseline`; the judge on new unclear turns after each pass |
| gcp | data agents, free until 2026-12-31 | `native-kc-max` (#360); `native-bare`, the floor (#372); `native-context-bare` with `BET_DATA_AGENT_MODEL=LATEST_GA_MODEL`, then `BET_DATA_AGENT_THINKING=THINKING`, then `FAST` (the API refuses latest-GA with thinking) |
| claude | Anthropic credits | Usefulness first (owner, 2026-11-04: "Prefer most useful run/eval/test over just for the sake of completeness ... opus only if we have credits left"): a pass that can move a verdict or answers an owner question runs before one that only fills a cell. Done 2026-11-04: Haiku `native-mcp`, `custom-toolbox`, `custom-hybrid` (#373); Sonnet `native-mcp` (both sets: its frozen pair reads worth building, so its hard set decides), `custom-toolbox`; Opus `custom-metricflow` on the frozen set (rerun after the audit failure). Not run, for the stop: Opus `custom-metricflow`'s hard set, Opus `native-mcp`, Sonnet `native-mcp`'s third hard run; each pass `--dollars` from its measured cost a case-run times its runs, plus half; Opus `native-mcp` only if the $90.00 stop leaves room for it (measured 2026-11-04: Sonnet `native-mcp` $0.089 a case-run, Haiku's $0.006; Opus would be about $75 for both sets, so it is listed as not run, with that reason) |
| subagents | the owner's Claude subscription (no API credits), #374 | `cc-metricflow`: Claude Code subagents (Agent tool, `model` haiku, then sonnet, then opus) on batches of about 12 cases from `374_cc_agent.py --batches`, each told by `probes/374_cc_prompt.md`, at most about 11 at once; scored with `328_mcp_live.py --agent 374_cc_agent.py --no-canary`; one test batch first per model, read before the rest; stop the lane when the session's own usage limit nears (save-work first) |
| local | none | after the passes: #333 (RULE.md step 3 named in `eval.md`), then #336 (the report, every arm and model the passes reached) |

- The subagent lane (owner, 2026-11-04T23:13Z, in a session, before 18 hours away): "you can spawn claude code subagents to gather more data points, complete the remaining runs ... I allow for haiku and sonnet. You need my approval for opus run that are more than 20 runs. For each setup you can have roughly 20 opus runs"; and "keep updating the report as you gather more ... and revise it. Keep it available in the issue on GH".
  - Haiku and Sonnet subagents run without asking; Opus takes at most about 20 new runs a setup, the rest waits for the owner's go.
  - One fresh subagent per case (the session effect measured on 2026-11-04), at most about 11 at once, the answers pushed after every wave.
- The report and the free lane (owner, 2026-11-04T20:15Z, in a session): "we should absolutely start with k is equal to 1 ... eventually ... full lane k is equal to 3"; "I don't want to rush towards having such a verdict in a way that we would close ... the entire research epic, and the entire even repository of any ideas"; "every time I have a new quota replenished on OpenRouter, I would still collect more data ... and update the report accordingly ... easy to update by only appending new data points without redoing heavy work on the report itself".
  - The free lane runs every pass in its row at k = 1 on both sets first (about 2,300 requests, about three daily quotas), then the same passes to k = 3 (about 5,700 more); each 00:00Z reset spends up to 850 of the day's 1,000.
  - The report lands from the data on hand (a first version by 2026-11-05T08:00Z) and is regenerated, never rewritten, after every later pass: `docs/research/semantic-bet/report/` builds `REPORT.md` and the HTML page from `results.json` alone, so a new pass only reruns the build and republishes; prose that a new number could contradict is written as a template over `results.json`, not by hand.
  - The report reads as the state of the evidence on a date, never a closing verdict: each finding says what would move it, and the epic, the track and the repo stay open for new ideas.
  - Its form (owner, 2026-11-04T20:40Z): a decision map first, then the brief's questions; designed with the `frontend-design` and `impeccable` skills against AI-slop looks, for data lovers and newcomers alike; three Opus designers drafted variants on the same brief, the owner picks one, then it is built in full.
    The medium (left to the agent, decided 2026-11-04): one static, self-contained HTML page built by a standard-library Python script from `results.json` and the logs, published to the same claude.ai URL after each pass; no Streamlit, since it needs a server we would keep (the brief's rule) and a page rebuilt from data needs none.
  - Merges (left to the agent, decided 2026-11-04): #310, then the train #337, merge once the k = 1 lane has run and the report is rebuilt from it; the k = 3 passes and their rebuilds go on a fresh `claude/semantic-bet` train from `main`, so the stack on #310 stops drifting from `main`.
- The owner, 2026-11-05T19:50Z, in a session: "it's nice to be precautious and careful about Claude API (which I won't replenish) and GCP billing, but not Openrouter which is already free and gets replenished 1,000 requests daily every day, so no need to stop earlier. try to utilize it more efficiently, despite incomplete runs, try to handoff better accordingly"; on Opus subagents: "let's do 50 for now"; on the two setup sections: "I wanna keep both for now".
  - The free lane spends up to 990 of the day's 1,000 (a pass checks its share before each case, so its last case may overrun by its own calls) and runs every pass from the top each day, k = 1 then k = 3, each pass skipping itself once its log is whole; Lightdash comes last in each round, and the lane skips it, not as an anomaly, when its 15 GB image cannot start.
  - A daily scheduled wake at 00:07Z (a fresh session: on 2026-11-04 every wake bound to an existing session failed at fire time with `ACCESS_DENIED`) runs the lane, rebuilds and republishes the report after each pass, and ends with a dated handoff block in `findings/free-lane-days.md` (free count, per-pass counts against the set, the pass mid-way, "Next:"), which the next wake reads first.
  - Opus subagents: up to about 50 runs a setup without asking; more needs the owner's go.
- The free lane's order from 2026-11-06 (epic #375's plan, the owner's go at 09:16Z, #379): v1's k = 1 round (what is left: `baseline`, `custom-lightdash`), then the hard set v2 (`hard-v2`, RULE.md § Set versions) at k = 1, then at k = 3, for `custom-hybrid`, `custom-metricflow`, `native-mcp` and `baseline`, each after `semantic_agent.bet_carry` copies v1's runs of its unchanged cases (a refused case is an anomaly), then the frozen set's k = 3 round; v1-hard's k = 3 round is dropped, since `hard-v2` supersedes it.
  The gcp lane runs `hard-v2` for `native-bare`, `native-context-bare`, `native-context` and `native-kc-max`, k = 1 then k = 3; the report shows v1 until the owner's go on #380 (`report/build.py --show`).
- Stop a lane on an anomaly, first in the handoff: GCP, `make gcp-cost-check` exit 1 or 3, any month cost above the $0.000010 known on 2026-11-04 or a new SKU, or `make gcp-usage-check` failing; Claude, a billing or credit error, a refused key, an unexpected 429, a pass over its budget, a case-run over 10x its arm's median dollars, or total spend past $88.00 (owner, 2026-11-04, the Console at $18.12 left and 81% of the month's limit: "plan accordingly no need to hit the literal 100"; the ledger plus $3.0704 unlogged is the total, within $0.33 of the Console at 19:10Z). The Claude lane is closed at about $88 (2026-11-04: Sonnet `native-mcp`'s hard set stopped at k = 2): no new Claude pass unless the owner raises the stop; OpenRouter, a spent free quota is no anomaly: the lane waits for 00:00Z.
- Merge (owner, 2026-11-04; timing as decided above): once #336's report is on the train, rebuilt from the k = 1 lane, and `make check` passes on its head, merge #310, then the train #337, each with a merge commit; then the digest says "Report ready".
- The daily query fence is 204,800 MiB (`QueryUsagePerDay`, raised by the owner, read 2026-11-04T17:31Z): it no longer limits a day's lanes; the month's free 1 TiB does, through `make gcp-usage-check`.

## Known conditions

- The $0 guard refuses every `gcloud dataplex` call, `--help` included, and this session's gcloud (570.0.0) is older than the dbt import needs (586.0.0): read the import's flags from its docs page, never from the CLI; seen 2026-11-03.
- MetricFlow's `CLIConfiguration.setup` (the `mf` CLI, `dbt/scripts/build_catalog.py`) runs dbt's connection test, `select 1`, and the proxy's injected Google credential carries it to BigQuery even on the compile-only `bigquery` target (refused: no project `pplk8s-lab`; `BigQuery adapter:` in the copy's `logs/dbt.log` tells it): never point that target at the lab project; [#339](../../../../issues/339) removes the test; seen 2026-11-03.
- A day's data-agent passes can spend the project's daily query fence (`QueryUsagePerDay`, 31,457 MiB a day, never raised; it resets at 00:00 Pacific): every query is then refused, not billed, the cost check's own billing-export query too (`gcp-cost-check: UNKNOWN: the billing export query failed`, exit 3), so GCP work ends until the reset; `make gcp-usage-check` stays ok because it measures the month; seen 2026-11-03T22:03Z, before the owner raised the fence to 204,800 MiB (§ The completion plan).

- A local pass (`bet_eval`'s `custom-metricflow`, `custom-hybrid`) needs `DBT_HOST=localhost DBT_PORT=5433` from the host, else every metric query is withheld for its unwritten audit row and the agent declines honestly, which scores as a real outcome: `bet_eval` now defaults them and refuses to start when the audit or metrics login does not connect; seen 2026-11-04 (an Opus pass, 219 of 288 runs, $16.31 unusable).

- Every pass asks a canary first (`bet_eval.canary_case`: the set's first single-turn `covered` case, unlogged, two tries) and stops with exit 2 when an arm misses it twice, so a broken warehouse, agent or model costs two case-runs instead of a pass; an exit 2 is an anomaly for the handoff (fix the cause, never pass `--no-canary` to get past it); added 2026-11-04 after the Opus pass that spent $16.31 on withheld answers.

## Never

- Merge, except § The completion plan's two merges; push any branch but `claude/semantic-bet` (and `claude/wip/*` snapshots, cloud's `save-work.sh`).
- Spend: paid GCP, paid OpenRouter models, Claude beyond the owner's budget.
- Work on Looker; employer data (`CLAUDE.md`'s clean-room rule).
