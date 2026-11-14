# Autopilot profile — pplk8s

Unattended cloud wakes on this repo follow the `cloud:autopilot` skill (if missing, read `cloud/skills/autopilot/SKILL.md` in the collection's clone, which `~/.claude/CLAUDE.md` names) with the slots below.
A wake with no `~/.claude/cloud-target` (the environment's setup didn't run) first runs `bash <clone>/cloud/setup.sh pplk8s`.
The routine prompt: "Follow `docs/agents/autopilot.md` in pplk8s and do one wake." (optionally "on #n").
Standing permission (owner, 2026-10-13): push `claude/<n>-<slug>` branches, open and edit PRs and issues, comment, label and mark PRs ready, without asking.
Every item is one branch `claude/<n>-<slug>` and one PR, reviewed by the `review` skill and merged by the wake once its gates and review records pass, unless the merge policy holds it.

## Merge policy

The wake merges a reviewed PR (`merge.sh`) except:
- `needs-local-verify`: a change a `local` gate covers waits until a local session passes its checklist and lifts the label.
- `needs-owner`: anything that costs money, raises a quota, cap or budget, or is costly to undo stays the owner's to merge.
`export AUTOPILOT_HOLD_LABELS="needs-user"` before the scripts: open issues still carry `needs-owner` under that older name.
A routine prompt that says never merge is stricter and wins: `export AUTOPILOT_MERGE_POLICY=owner` for that wake.

## Review

The paths that set a review tier: `REVIEW.md` at the repo root, read from the default branch by the `review` skill's `tier.sh`.

## Digest

Steering lines (SKILL.md § Steering) at the top of [the digest issue](../../../../issues/43)'s body, which only the owner edits; with no `Mode` line a wake runs `offline`. Open owner questions are the `needs-owner` issues.
- `offline` keeps a wake off the lab's GCP project: no `make` target whose help starts with `Live` (`bigquery-live-check`, `gcp-plan`, `gcp-images`, `gcp-cost-check`, …), no live data-agent or Knowledge Catalog call, and no issue whose work needs one; the offline `gcp-validate` and `gcp-image-check` (the BigQuery emulator) stay gates.
- `full` adds the free-tier GCP map's live steps, which wait for a wake the owner watches, because the billing export lags hours behind a cost.

## Queue

Maps are open `wayfinder:map` issues, named here by title; each map's `autopilot-ready` sub-issues go in its table's order.
1. `agent:ready` issues labelled `bug`, then `lesson` (a lesson for the GKE or Composer build, researched from primary sources: one line with its evidence and sources as a `🤖` comment on the issue, which the wake then closes; no file changes).
2. *Map: the questions business users ask*, then *Map: one governed semantic layer for every agent*.
3. *Map: the semantic track on a free-tier GCP project* (`Mode: full` only), under `platform/gcp/README.md`; an offline wake with nothing else pickable ends, never falling through to it.
4. Low priority: *Map: an eval that measures what each approach is worth*, then the research issue on moving the semantic track to dbt v2.

Until the labels are renamed, read `autopilot-ready` as `agent:ready`, `needs-user` as `needs-owner`, and a `🤖 Autopilot handoff` or `🤖 Autopilot claim` comment as the skill's `🤖 Handoff` and claim.

## Gates

`cloud` (every wake runs them; the stamp's command first, the path-bound ones before the stamp, a red one blocks the merge; counts in the handoff):
- `make tools && make check` (the stamp: `make lint` and `make test`, the alert rules' promtool tests included, with the Compose warehouse up and required)
- `make verify`: every image build (`BUILD_CA` passes the proxy's CA to the dependency steps)
- `dbt/**` changed: dbt from the host, `cd dbt && DBT_HOST=localhost DBT_PORT=5433 DBT_PROFILES_DIR=$PWD uvx --from dbt-core==1.12.6 --with dbt-postgres==1.11.0 dbt …` (add `--with dbt-metricflow[dbt-postgres]==0.15.0` for `mf`), and `make gcp-image-check`
- `services/el-factory/**` changed: `uv run gunicorn` from the host with the env from `scripts/el-factory-local.sh`
- `platform/k8s/**`, `platform/kind/**` or a workload image changed: `make cluster-up`, `make workloads-up`, and `make agent-deploy-check` for the semantic agent
- `airflow/**` or `platform/helm/**` changed: `make ci-integration`, and the exit checks the change touches, with `DAG_DELIVERY=local`
Each wake has its own container; run the long gates one at a time (`run_in_background`), once on the PR's final head.

`local` (an agent on the owner's laptop runs them from the handoff's checklist; the PR waits on `needs-local-verify`):
- git-sync delivery, when a change touches it: `make airflow-up` with the default `DAG_DELIVERY=git-sync` (the laptop's deploy key) — expect: the rollout Ready and `main`'s DAGs parsed.
- a WSL2-specific check, or one that does not fit the session's disk: the command the handoff names — expect: its `passed` line.
A checklist that runs a DAG the PR changes deploys it with `DAG_DELIVERY=local make airflow-up`: git-sync serves `main`, so it would test the old DAG.

## Never

- Start a paid or quota-bound eval pass (`make agent-eval`, `make record-call-labels`) except through the `experiment-preflight` skill, on free models only.
- Raise a GCP quota, spend cap or budget; run a live GCP step without `make gcp-cost-check` before and after, whose exit 1 (a cost) or 3 (not provable yet) ends the wake's GCP work with the SKU or the reason in the handoff; run an owner's step (`make gcp-up`, `gcp-down`, `gcp-workloads-up`): it is `needs-owner`.
- Dispatch a GitHub workflow: they run on demand only.
- Add to the frozen history (`PLAN.md`, `semantic/PLAN.md`, `LESSONS.md`, `LEDGER.md`, `ledger.d/`); a routine prompt asking for a fragment or a lessons line gets a `🤖` comment on its issue instead, listed under `Went wrong:` as `setup`.
- Pin an image tag by hand in the `Makefile`: `scripts/image-tag.sh` computes each tag from its build inputs.
- Change a choice the files describe without rewriting its present-tense reason in the same PR.

## Known conditions

- Open issues still labelled `in-train` hold work that sits on the unmerged `claude/semantic-bet` branch: `gh api "repos/<o>/<r>/issues?labels=in-train&state=open"` lists them; pick none until that branch lands as reviewed slices or closes and the label goes; seen 2026-11-14.
- `docker build` steps reach PyPI through the TLS-intercepting proxy only with its CA: `make` passes it as the BuildKit secret `build_ca` when `BUILD_CA` (default `/root/.ccr/ca-bundle.crt`) exists, so build through `make`, never a plain `docker build`; seen 2026-10-30.
- A fresh session rebuilds every image: builds share a per-image layer cache at `ghcr.io/<owner>/<repo>/<image>:buildcache` (Makefile `BUILD_CACHE`, on by default on cloud; the `image-cache` skill); seen 2026-10-30.
- kind fails on the sandbox's cgroup v1 without `CAP_SYS_RESOURCE`: `cluster-up.sh` adapts the kubelet and containerd; seen 2026-10-30.
- kind nodes and pods cannot reach the internet through the host's loopback `HTTPS_PROXY`: `make egress-up` (run by `cluster-up` and every deploy target) relays the kind gateway to the proxy through the `kind-egress` container, gives containerd the proxy's CA, and sends docker.io pulls to mirror.gcr.io; seen 2026-10-31.
- `no space left on device` (the session's disk is about 39 GB): `make push` and `airflow-image` skip a tag the local registry serves and drop Docker's copy after a push (`FORCE_BUILD=1` rebuilds an unchanged one); run `docker builder prune -af` and remove old tags' images; seen 2026-10-31.
- Exporters publish no host port: read one with `docker run --rm --network pplk8s curlimages/curl …`; seen 2026-10-14.
