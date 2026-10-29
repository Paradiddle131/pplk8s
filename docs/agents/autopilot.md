# Autopilot protocol — `pplk8s-worker` cloud runs

This file is the standing brief for unattended Claude Code runs on this repository (cloud routines started on a schedule while the user is away).
The routine prompt only says "follow `docs/agents/autopilot.md`"; everything that can change lives here, versioned with the code.
Repo [`CLAUDE.md`](../../CLAUDE.md) still binds; where it assumes the user's machine, this file says what to do instead.
This is v0: the generic parts move into an `autopilot` skill in `Paradiddle131/claude-dotfiles` ([Map: reusable autopilot for cloud routines](https://github.com/Paradiddle131/claude-dotfiles/issues/1)), and this file then shrinks to the pplk8s profile.

**Standing permission (granted by the user, 2026-10-13):** on `Paradiddle131/pplk8s`, runs may push `claude/*` branches, open and edit draft PRs and issues, comment, add and remove labels, and mark PRs ready.
Do these without asking.
The same holds on `Paradiddle131/claude-dotfiles` for its map's tickets (packets, prototype branches, research and build PRs) (user, 2026-10-14); that repo has no `needs-user` label, so a packet there is marked by assigning the ticket to `Paradiddle131`.
**Never merge a PR** (user decision, 2026-10-12): pplk8s's real exit checks need the local kind cluster, so every finished PR hands off for local verification (§6).

A run can be cut off at any moment by a 5-hour or weekly usage limit, and other runs may be working beside you (runs start hourly and overlap).
Design every step so the next run can pick up exactly where this one stopped: push early, push often, keep the handoff current.

## 0. The environment you are in

- Clones of `Paradiddle131/pplk8s` and `Paradiddle131/claude-dotfiles` on a cloud VM, on `main`; the session may start in the folder above them, so `cd` into the pplk8s clone first.
  `claude-dotfiles` holds the user's skills; the setup script ([`cloud-setup.sh`](cloud-setup.sh)) links a subset into `~/.claude/skills`.
  Check `ls ~/.claude/skills`; if a skill named below is missing, read its `SKILL.md` from the dotfiles clone directly and say so in the handoff.
  The `research` skill is not available on cloud: research with WebSearch/WebFetch and primary sources yourself.
- GitHub: REST only.
  `gh pr …` and `gh issue …` fail (the cloud proxy rejects GraphQL); use `gh api`:
  - open issues: `gh api 'repos/Paradiddle131/pplk8s/issues?state=open&per_page=100'` (entries with a `pull_request` key are PRs)
  - open PRs: `gh api 'repos/Paradiddle131/pplk8s/pulls?state=open&per_page=50'`; checks: `gh api repos/Paradiddle131/pplk8s/commits/<sha>/check-runs`
  - sub-issues of a map: `gh api repos/Paradiddle131/pplk8s/issues/<n>/sub_issues`; blockers: `gh api repos/Paradiddle131/pplk8s/issues/<n>/dependencies/blocked_by`
  - comment: `gh api repos/Paradiddle131/pplk8s/issues/<n>/comments -F body=@file.md`; edit: `gh api -X PATCH repos/Paradiddle131/pplk8s/issues/comments/<id> -F body=@file.md`
  - create a draft PR: `gh api repos/Paradiddle131/pplk8s/pulls -f title=… -f head=<branch> -f base=main -F draft=true -F body=@body.md`
  - labels: `gh api repos/Paradiddle131/pplk8s/issues/<n>/labels -f 'labels[]=autopilot'`
  - **Bodies from a file need capital `-F body=@file.md`**; `-f` posts the literal path.
    Read every body back after posting (`--jq '.body[0:80]'`).
  - Draft → ready: `gh api -X POST repos/Paradiddle131/pplk8s/pulls/<n>/ccr/ready_for_review` (a proxy route; plain REST cannot do it), or the GitHub MCP tool `update_pull_request` with `draft: false`.
  - `gh api search/…` is refused ("sessions are bound to their configured repositories"); list `repos/…/issues?state=all&per_page=100` and filter with `--jq`.
  - PR review threads: if REST `pulls/<n>/comments` answers 403, read them with the GitHub MCP `pull_request_read` (`method: get_review_comments`).
- **GitHub Actions is off** (PLAN.md D26, since 2026-10-29): no workflow runs on a push or a PR, and the account's Actions billing is blocked anyway, so a dispatched job fails in seconds.
  A PR shows no checks; that is expected: don't dispatch a workflow, don't re-file it.
  The gates are `make check` here (lint, unit and DagBag tests with the Compose warehouse up and required) and the laptop's `make verify` before merge.
- Start Docker first: `bash docs/agents/cloud-docker.sh` (idempotent).
  The VM does not start the daemon, the setup snapshot keeps no processes, and anonymous Docker Hub pulls hit 429, so the script starts `dockerd` with `mirror.gcr.io` as registry mirror.
- What runs on cloud: Docker and `docker compose`, `uv`, Postgres 16 (not started).
  So `make check` (`make lint` and `make test`, unit + DagBag, with the Compose services up) runs here.
- Image builds that `pip install` fail TLS through the agent proxy (pypi.org: `self-signed certificate in certificate chain`), so `make build`, `make verify` and `make phase1-check` do not run; the images are built by `make verify` on the laptop before merge (PLAN.md D26).
  Run dbt from the host instead: `cd dbt && DBT_HOST=localhost DBT_PORT=5433 DBT_PROFILES_DIR=$PWD uvx --from dbt-core==1.12.5 --with dbt-postgres==1.11.0 dbt …`; run EL Factory with `uv run gunicorn` and the env from `scripts/el-factory-local.sh`.
  Start a host gunicorn with `run_in_background` (or record its PID): one started in a plain Bash call outlives the tool's kill and holds the port.
- Alert rules over the Compose exporters are cloud-verifiable without kind: run `quay.io/prometheus/prometheus:v3.15.0` on `--network pplk8s` with the rule file extracted from the PrometheusRule's `spec` (as `tests/monitoring/rules-test.sh` does); read an exporter with `docker run --rm --network pplk8s curlimages/curl …` (exporters publish no host port).
  So a monitoring change (metric, rule, promtool test, dashboard, runbook) is buildable and mostly verifiable here; only its kind deployment is local.
- Every `uv` call warns `UV_NATIVE_TLS is deprecated`; the environment sets it, it is harmless, ignore it.
- What does not: kind (the VM is cgroup v1 and kubelet 1.36 refuses it; settled 2026-10-12), so nothing needing the cluster: `make airflow-up`, `phase2`–`phase6` checks, drills, KEDA, monitoring.
  The cluster check is `make ci-integration` on the laptop before merge; `integration.yaml` runs on GitHub Actions only on demand (D26), so do not dispatch it.
  Probe once per environment and record the result on the run board; don't spend a run fighting it.
- `~/.claude/CLAUDE.md` is claude-dotfiles' `cloud/CLAUDE.md` (linked by the setup script); Hindsight and the compound-engineer workflow are ignored on cloud.
- The setup script runs only when the environment's cache is rebuilt (an edit of its Setup field, or ~7 days), so a change to `cloud-setup.sh` reaches runs only after the user bumps the `cloud-setup vN` comment in that field; a change you make to it is a `You:` item in the handoff.
- Not on cloud: Hindsight, Atrium, the user's `~/.claude`, `localhost` services, the browser at `localhost:8080`.
  Skip Hindsight retains and Atrium registration; put durable facts in the PR/issue instead.
- Every `<UTC>` you write (board, claim, handoff, feedback) comes from `date -u +%FT%H:%MZ` at the moment you write it; never estimate it.
  The 75-minute liveness rule in §3 reads these stamps, so a stamp in the future makes a run look live after it ended.
- Commits: conventional messages, **no agent co-author trailer and no `Claude-Session:` trailer** (the setup script turns attribution off; check `git log -1` after your first commit and amend if a trailer slipped in).

## 1. Orient (read-only, keep it short)

1. `git fetch --all --prune`; list `claude/*` branches and branches with open PRs.
2. **The run board** [🤖 pplk8s-worker run board](https://github.com/Paradiddle131/pplk8s/issues/43): its comments edited in the last 75 minutes are **live runs**; note each one's item and areas.
   The board's issue body holds the **decision digest** (§4a): every question waiting for the user, across both repos.
3. Open PRs labelled `autopilot`: base, draft state, checks, the user's review comments, the `🤖 Autopilot handoff` comment.
4. The maps (labelled `wayfinder:map`): [Map: NYC TLC monthly pipeline](https://github.com/Paradiddle131/pplk8s/issues/35), and in `claude-dotfiles` [Map: reusable autopilot for cloud routines](https://github.com/Paradiddle131/claude-dotfiles/issues/1).
   Read the map bodies (Destination, Notes, Decisions so far), not every ticket.
5. Items labelled `needs-user` with a user comment newer than the last bot comment: those are fresh answers.
   The bot and the user post as the same login (`Paradiddle131`), so tell them apart by the body: a bot comment starts with `🤖`, a user comment does not.
6. [`PLAN.md`](../../PLAN.md) and the newest [`LEDGER.md`](../../LEDGER.md) entry.

Write a 5-line state summary to yourself before deciding.

## 2. Register on the board

Before choosing work, post your board comment (keep its id; you edit it all run):

```
🟢 run <UTC start> · <session URL if known>
item: (choosing)
areas: (none yet)
state: orienting
```

While §8 is in force, post your run-feedback comment now too (§8), before any real work.

## 3. Choose work — first match that doesn't conflict wins

An item **conflicts** with a live run when it is the same issue or PR, when one is blocked by the other, or when their **areas** overlap.
Areas are the repo paths a change touches, as globs (`services/el-factory/**`, `dbt/models/tlc/**`, `PLAN.md`).
`PLAN.md`, `LESSONS.md`, `.github/workflows/**`, `Makefile` and `airflow/include/pplk8s/**` (the seam) are **shared**: only one live run may hold each.
A claim on an item is **live** while the item or its PR saw a worker comment, comment edit or push in the last 75 minutes; a claim with nothing for 3 hours is abandoned — take it over and say so.

1. **Fresh user answers**: a `needs-user` item the user replied to. Act on the answer (see §4 for wayfinder tickets), remove `needs-user`.
2. **Unfinished autopilot work**: an `autopilot` PR whose handoff has open **Next** items and no live claim.
3. **Broken autopilot PRs**: a failing `make check` reported in the handoff, merge conflicts, or the user's review comments. Fix them on their branch.
4. **The wayfinder frontier**: on each map (§1.4, both repos), open sub-issues that are unblocked and unassigned, in map order (§4).
5. **Build issues** labelled `autopilot-ready` whose blockers are all closed, lowest number first; prefer one cloud can verify, and when a local-only build issue depends on a cloud-verifiable bug, take the bug first.
6. **Next best action**: a failing, flaky or skipped test; a lint warning; a `bug` issue; a `lesson` issue.
   Open an issue first if none exists, so the work is visible.
   An issue blocked by an architectural fork gets a §4 decision packet and `needs-user` instead of a build.
7. **Build ahead of an answer** (§4b): a `needs-user` packet whose recommendation is reversible and buildable on cloud, with no speculative PR yet.
8. **Refill the queue** (§4c) when 1–7 are empty, instead of exiting.

PRs waiting for local verification never limit new work; only dependencies do (user, 2026-10-13).
An item whose blocker is an open PR, not yet merged, is takeable: branch from that PR's branch and set your PR's base to it (§5).

**Build vs verify.** Needing kind or `make verify` to *verify* never makes an item untakeable: build it, verify what cloud can (§0, §6), and hand the rest to the laptop with `needs-local-verify`.
Only work that needs a live cluster *while building* (tuning against kind, a drill whose design depends on what the cluster does) is local-only, and even then the cloud-buildable parts (metrics, rules, tests, runbook text, scripts) are sliced out into their own tickets (§4c).

If every candidate conflicts with a live run, or three runs are already live: edit your board comment to `⚪ nothing non-conflicting; exiting` and end the run (it costs almost nothing, and the usage window stays for the live runs).
Exit for an empty queue only after §4c found nothing to file.

Never pick work only the user can do: a reversal of a recorded decision, anything an issue marks "ask the user", or running the local-only checks in §0.

## 4. Wayfinder tickets

Follow the `wayfinder` skill's "Work through the map" mode, with one change for unattended runs:

- **research** (AFK): resolve it fully. Findings go to `docs/research/<name>.md` in a docs-only PR from a `research/<name>` branch, so later code and docs can link a path on `main` rather than a branch; post the resolution comment, close the ticket, add the one-line pointer to the map's **Decisions so far**.
- **grilling / prototype** (HITL): **never resolve these yourself**, and never answer your own questions.
  Prepare a **decision packet** instead: read the code and facts the question needs, then comment on the ticket with the questions (at most three, the most blocking first), each with options **A/B/C**, one line of trade-off each, and **Recommendation:** with a short why.
  For a prototype, build the rough artifact on a `claude/<n>-<slug>` branch and link it by commit sha; if the harness insists on a PR, open it as a draft titled `prototype #<n> — do not merge`, and close it when the ticket resolves.
  End the packet with one line, **If you pick the recommendation, the build is:** (the change, its areas, how cloud verifies it), so §4b can start it.
  Label the ticket `needs-user`, add it to the digest (§4a), and move on.
  When the user has answered (§3 item 1), post the resolution comment, close the ticket, update the map, and graduate any fog the answer made specifiable into new tickets (create, then wire `blocked_by`).
- **task**: do it if it is AFK and cloud-verifiable; otherwise write the human a precise checklist on the ticket and label it `needs-user`.
- Claiming a wayfinder ticket = assigning it to `Paradiddle131` (the dev driving the map) **and** your board comment naming it.

These packets apply to any issue that needs a user decision, not only wayfinder tickets.

### 4a. Decision digest

The run board's **issue body** (#43) is the one place the user reads to unblock runs: every open question, across both repos, one line each, most blocking first.

```markdown
## Waiting for you (answer on the issue, like `1B 2A`)
- [ ] #66 — 3 questions: producer location, checks vs unpaused DAG, soak — recommended `1B 2A 3B` — unblocks: the partner producer build
- [ ] PR #84 — confirm D37 — recommended: yes — unblocks: merge
## Waiting for the laptop
- [ ] PR #81 — `make verify`, merge
```

Edit it whenever you post, answer or resolve a packet, or mark a PR `needs-local-verify`: re-read the body right before you write it (another run may have edited it), change only your lines, write it back with `gh api -X PATCH repos/Paradiddle131/pplk8s/issues/43 -F body=@digest.md`.
Remove a line when its item is resolved or merged.

### 4b. Build ahead of an answer

A packet's recommendation is usually what the user picks, so an unanswered packet need not stall its build.
Take it (§3.7) when all hold: the recommended option is reversible (no data deleted outside the lab, no recorded decision reversed), cloud can build it, and it has no speculative PR yet.

- Branch `claude/<n>-<slug>`, draft PR titled `[speculative: <n> = <answer>] …`, body `Refs #<n>` (not `Closes`).
- Write the PLAN.md decision as the packet recommends, marked `(proposed, awaiting #<n>)`.
- The handoff's **You:** line: "answer #<n>; if you pick `<answer>`, this PR is its build".
- Keep `needs-user` on the issue. When the user picks the recommendation, the next run drops `speculative` and `(proposed …)` and finishes the PR as usual; when they pick otherwise, close the PR with a comment and build the chosen option.
- At most one speculative PR per packet; never stack a speculative PR on another speculative PR.

### 4c. Refill the queue

When §3.1–3.7 are empty, file work instead of exiting, first match wins, **at most three new issues per run**:

1. **Slice** an open issue that mixes cloud-buildable and local-only work (§3, build vs verify) into sub-issues: one per cloud-buildable part, `autopilot-ready`, and the local run as the last one, wired with `blocked_by` (`gh api repos/…/issues/<n>/sub_issues -F sub_issue_id=<sub-issue id, not number>`; `gh api repos/…/issues/<n>/dependencies/blocked_by -F issue_id=<blocker id>`).
2. **Reality-check** a claim in `PLAN.md` or `docs/research/**` that cloud can measure (a file schema, a size, a version, an upstream behaviour); #82 is the model. A wrong claim becomes a `bug` issue with the evidence.
3. **Close a test gap**: a code path in `airflow/include/pplk8s/**`, `services/**` or `dbt/**` that no test exercises, or a skipped test.
4. **Research a lesson**: for an open `lesson` issue, or a `LESSONS.md` line with no GKE/Composer source yet, find the primary-source answer for Stage 2/3 (a docs-only `research/<name>` PR, as §4 research tickets).

Work inside approved scope (a PLAN.md phase's exit criteria or bullet, a §6 risk, an open issue's acceptance) gets `autopilot-ready` and can be taken by the same run.
New scope (a feature, a phase, a dependency the plan does not name) gets the label `proposed` and a digest line, and is never built until the user removes `proposed`.
Each filed issue carries symptom or goal, evidence, acceptance and its areas.

## 5. Claim and work

1. Edit your board comment: `item:` (name + link), `areas:` (globs), `state: working`.
2. Re-read the board: if another live run claimed the same item or overlapping areas **earlier** than you, yield: edit your comment, go back to §3.
3. Comment on the item `🤖 Autopilot claim — <UTC> — <one line of intent>`, add the `autopilot` label.
4. Branch `claude/<issue>-<slug>` from `main` (or from the branch of the PR you depend on; set the PR base to it).
   Ignore the session branch the harness assigns (`claude/<adjective>-<name>-<suffix>`); never push it.
5. Follow `CLAUDE.md` and `PLAN.md`: change a decision in `PLAN.md`, with its rationale, before acting on it.
6. After the first meaningful commit, push and open a **draft PR** (`Closes #<n>` in the body), so the work survives a cut-off.
   Push after every working step and edit your board comment's `state:` line each time (that edit is your heartbeat).
7. **Shared logs:** never edit `LEDGER.md`; add your entry as a fragment `ledger.d/<YYYY-MM-DD>-<n>-<slug>.md` in your PR (`ledger.d/README.md`), so it merges with the work and parallel PRs never conflict.
   Append to `LESSONS.md` only when your areas hold it.
8. Put the `lesson` label on any issue or PR whose work likely teaches a GKE (Stage 2) or Composer (Stage 3) lesson (see `CLAUDE.md`).

## 6. Verify and hand off

**Verify what cloud can**, and never claim more: `make check` (lint, unit and DagBag tests with the warehouse required), and host-side dbt or EL Factory (§0) when you touched them or the Compose services; image builds and kind are left to the local `make verify` / `make ci-integration`.
A change to an image's contents (a Dockerfile, dependencies, dbt models, service code, and `airflow/include/**`, which the Airflow image bakes in for `DAG_DELIVERY=local` and `make ci-integration`) bumps that image's tag in the `Makefile` (PLAN.md D16), or the lab keeps running the cached old image (#92: #56 and #57 changed the seam without a bump).
Actions is off (§0): `make check` is the PR's light check, quoted in the handoff. Do not dispatch the on-demand `test`, `images` or `integration` jobs.

Keep exactly one comment per PR titled `🤖 Autopilot handoff`, edited in place after every push.
**The part outside `<details>` is for the human scanning many PRs: only what needs them, five lines at most.**
Everything else goes inside the collapsed sections.

```markdown
🤖 Autopilot handoff — <UTC> — **<in progress | ready for local verify | blocked>**

**You:** <the one thing the user must do or decide, or "nothing yet">
**Result:** <one line: what this PR does, verified how far>

<details><summary>Local verification checklist</summary>

- [ ] `git fetch && git switch claude/<n>-<slug>`
- [ ] `make <targets>` — expect: <exact evidence: row counts, alert names, run states>
- [ ] Merge (the ledger fragment is in the PR).

</details>
<details><summary>Agent context (resume here)</summary>

**Done:** …
**Next:** - [ ] … (in order)
**Verified on cloud** (each gate ticked with its evidence, or unticked with `n/a (cloud)` / `not run: <why>`):
- [ ] `make check` — <passed counts> (lint, unit and DagBag tests, warehouse required)
- [ ] host dbt / EL Factory (§0) — <what ran, row counts>
**Not verified (needs local):** `make verify` (image builds), `make ci-integration` when cluster-facing, …
**Decisions taken and why:** …
**Ledger fragment:** `ledger.d/<file>`

</details>
```

When the work is complete and cloud-verified: mark the PR ready (MCP `update_pull_request`, `draft: false`), label it `needs-local-verify`, set the headline to **ready for local verify**.

**Local resume** (a session on the laptop, user decision 2026-10-14):

1. List open PRs labelled `needs-local-verify`, oldest first, stacked bases before the PRs on top of them; take one.
2. Read its handoff's agent section, run the checklist.
3. Edit the handoff **in place**: tick each local box with its evidence; headline → **verified locally — merge**, or **local verify failed** with a `You:` line and new **Next** items (a failed verify hands the PR back to the cloud runs, §3.2).
4. Remove `needs-local-verify`, update the digest (§4a); after the merge, `make ledger` on `main` folds the fragments.

## 7. End of run

- Leave the tree clean: everything committed and pushed, or deliberately discarded.
- Finish your §8 feedback comment (while §8 is in force).
- Edit your board comment to `⚫ ended <UTC>` with the items touched and what the next run should do first; make sure the digest (§4a) matches what you left waiting.
- Every problem you found but did not fix gets an issue (symptom, evidence, suspected cause, acceptance).
- Your final message: what you worked on, links, the next run's first step.
- With budget left and nothing finished blocking you, go back to §3 instead of ending.

## 8. Run feedback (temporary: the first runs)

**In force until the user removes this section.** These are the first unattended runs; the user learns from each one what to fix in this brief, the setup script and the routine.
The VM disappears when the run ends, so feedback lives only on GitHub: one comment per run on [🤖 pplk8s-worker run feedback (first runs)](https://github.com/Paradiddle131/pplk8s/issues/45).

- Post it at the start of the run (right after registering on the board), with the probes filled in, then **edit it in place** after every working step, so a run cut off by a usage limit still leaves its feedback.
- Be specific and honest: a command and its output beats an adjective; say what you guessed.
- For every blocker or friction, write the answer that would have removed it if you know or found it (a setting, an allowlist host, a missing tool, a corrected sentence in this file), and a concrete patch when it is a text change.
  Don't apply patches to this file or the setup script yourself unless that is the work item you claimed.
  A pure correction of a fact in §0 (an environment probe result, a REST route, a recipe that changed) is takeable as §3.6 work: open an issue, apply it in a PR. A change to how runs choose, claim or hand off work stays a proposal for the user.
- Probe the open environment facts once per run (cheap commands only; stop at the first answer):
  - layout: `pwd` at start, `ls /home/user`, where the two clones are;
  - skills: `ls -la ~/.claude/skills` (links resolve into the fresh clone?), `cat ~/.claude/settings.json`;
  - attribution: after your first commit, `git log -1 --format=%B` (any `Claude-Session:` or co-author trailer?);
  - Docker: `docker info` and `docker run --rm hello-world`;
  - kind: `kind create cluster --name probe --wait 120s` then `kind delete cluster --name probe` (install with `scripts/install-tools.sh` if missing); record the first error verbatim;
  - GitHub: does `gh api` REST work, does `gh issue list` fail, can it read a job log? (Do not dispatch a workflow to find out: a dispatch runs the heavy jobs, D26.)
  - network: any host the run needed that was blocked (`curl -sI https://<host>`).
  Skip a probe whose answer an earlier comment on the feedback issue already settled, and say so.

```markdown
🤖 Run feedback — <UTC start> — <session URL if known> — **<went well | partly | blocked>**

**Outcome:** <one line: what the run achieved>
**Blockers:** <one line each, or "none">
**Top fix:** <the single change that would most improve the next run>

<details><summary>How it went</summary>

Timeline: orient → choice (and why) → work → verify → handoff, with rough durations and where time went.
What in this brief was unclear, wrong or missing; what worked well and should stay.

</details>
<details><summary>Blockers and how to resolve them</summary>

| Blocker | Evidence (command → output) | Known or likely resolution | Who: brief / setup script / routine config / user |
|---|---|---|---|

</details>
<details><summary>Environment probes</summary>

| Probe | Result |
|---|---|

</details>
<details><summary>Proposed patches</summary>

Diff-style text changes to `docs/agents/autopilot.md`, `docs/agents/cloud-setup.sh`, the routine prompt, or its network allowlist.

</details>
```
