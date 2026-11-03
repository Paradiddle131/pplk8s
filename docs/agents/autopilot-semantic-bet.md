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
- A `ledger.d/` fragment per finished issue; lessons for work go to `semantic/PLAN.md` § 6 only with the final report.

## Gates

- Docs only: `git diff --check`.
- Probes: `uvx ruff@0.17.0 check docs/research/semantic-bet/probes && uvx ruff@0.17.0 format --check docs/research/semantic-bet/probes`.
- `services/semantic-agent/**` changed: `make agent-test`; `dbt/**` changed: dbt from the host as `autopilot.md` § Gates says; any code: `make lint`.
- `make check` once on the train's head before the final report lands.

## The final report

- [#336](../../../../issues/336): `docs/research/semantic-bet/REPORT.md` and an HTML version (an artifact on Map #324, and a published page when the Artifact tool exists), answering every register question with evidence or "still unknown", with the verdict.
- When it lands, the digest says "Report ready" and the wake's final message starts with `OWNER NEEDED: report ready; read it and turn the routine off`.

## Known conditions

- The $0 guard refuses every `gcloud dataplex` call, `--help` included, and this session's gcloud (570.0.0) is older than the dbt import needs (586.0.0): read the import's flags from its docs page, never from the CLI; seen 2026-11-03.
- MetricFlow's `CLIConfiguration.setup` (the `mf` CLI, `dbt/scripts/build_catalog.py`) runs dbt's connection test, `select 1`, and the proxy's injected Google credential carries it to BigQuery even on the compile-only `bigquery` target (refused: no project `pplk8s-lab`; `BigQuery adapter:` in the copy's `logs/dbt.log` tells it): never point that target at the lab project; [#339](../../../../issues/339) removes the test; seen 2026-11-03.
- A day's data-agent passes can spend the project's daily query fence (`QueryUsagePerDay`, 31,457 MiB a day, never raised; it resets at 00:00 Pacific): every query is then refused, not billed, the cost check's own billing-export query too (`gcp-cost-check: UNKNOWN: the billing export query failed`, exit 3), so GCP work ends until the reset; `make gcp-usage-check` stays ok because it measures the month; run one lane and at most two data-agent arms a day, about 1 GiB kept for the cost check; seen 2026-11-03T22:03Z.

## Never

- Merge; push any branch but `claude/semantic-bet`.
- Spend: paid GCP, paid OpenRouter models, Claude beyond the owner's budget.
- Work on Looker; employer data (`CLAUDE.md`'s clean-room rule).
