# Autopilot profile — pplk8s

Unattended cloud wakes on this repo follow the `cloud:autopilot` skill (if missing, read `cloud/skills/autopilot/SKILL.md` in the collection's clone, which `~/.claude/CLAUDE.md` names) with the slots below.
A wake with no `~/.claude/cloud-target` (the environment's setup didn't run) first runs `bash <clone>/cloud/setup.sh pplk8s`.
The routine prompt: "Follow `docs/agents/autopilot.md` in pplk8s and do one wake." (optionally "on #n").
Standing permission (owner, 2026-10-13): push `claude/*` branches, open and edit PRs and issues, comment, label, mark PRs ready, without asking.
Every item is one branch `claude/<n>-<slug>`, the only branch a wake pushes, and one PR, reviewed by the `review` skill and merged by the wake once its gates and review records pass, unless the merge policy holds it.

## Merge policy

The wake merges a reviewed PR with `AUTOPILOT_HOLD_LABELS=needs-user $AP/scripts/merge.sh <pr>` (the prefix on the command itself, since no variable carries between calls; `merge.sh` then also holds a PR that carries `needs-user`, the older name of `needs-owner`) unless one of these holds it:
- `needs-local-verify`: a gate the session cannot run (a `local` gate, or a `cloud` one a blocked host stops) waits for a local session to run it from the handoff's checklist and lift the label.
- `owner-merges`, which the wake puts on the PR itself and never removes: a PR that costs money, raises a quota, cap or budget, or is costly to undo; its issue carries the decision packet and `needs-owner`, and only the owner's own merge lands it.
  Always such a PR: one that touches `platform/gcp/infra/**`, the `caps` in `platform/gcp/free-path.yaml`, the cost check (`platform/gcp/cost-check.sh`), or a `make` target whose help calls it the owner's step, or that changes a byte cap or the free-model guard (`maximum_bytes_billed` in `dbt/profiles.yml`, the `BQ_MAXIMUM_BYTES_BILLED` default in `services/semantic-agent/src/semantic_agent/warehouse_bigquery.py` and `tests/e2e/lib/bigquery_target.py`, the `:free` check in `services/semantic-agent/src/semantic_agent/model.py`).
Agent PRs opened before this profile stay the owner's to merge: a wake that resumes one labels it `owner-merges`.
A routine prompt that says never merge is stricter and wins: that wake prefixes `AUTOPILOT_MERGE_POLICY=owner` to the same command, which then stops at ready.

## Review

The paths that set a review tier: `REVIEW.md` at the repo root, read from the default branch by the `review` skill's `tier.sh`.

## Digest

Steering lines (SKILL.md § Steering) at the top of [the digest issue](../../../../issues/43)'s body, which only the owner edits; with no `Mode` line a wake runs `offline`.
A wake reads that body and never edits it, whatever older notes in it invite.
Open owner questions are the `needs-owner` issues.
- `offline` keeps a wake off the lab's GCP project: no `make` target whose help starts with `Live` (`bigquery-live-check`, `gcp-plan`, `gcp-images`, `gcp-cost-check`, …), no live data-agent or Knowledge Catalog call, and no issue whose work needs one; the offline `gcp-validate` and `gcp-image-check` (the BigQuery emulator) stay gates.
- `full` adds the free-tier GCP map's live steps, which wait for a wake the owner watches, because the billing export lags hours behind a cost.

## Queue

Maps are open `wayfinder:map` issues, named here by title; each map's `autopilot-ready` sub-issues go in its table's order.
An issue labelled `semantic-bet` is not pickable: its work builds on the open `claude/semantic-bet` branch, so it waits until that branch has landed as reviewed slices or closed.
1. `agent:ready` issues labelled `bug`, then `lesson` (a lesson for the GKE or Composer build, researched from primary sources: one line with its evidence and sources as a `🤖` comment on the issue, which the wake then closes; no file changes).
2. *Map: the questions business users ask*, then *Map: one governed semantic layer for every agent*.
3. *Map: the semantic track on a free-tier GCP project* (`Mode: full` only), under `platform/gcp/README.md`; an offline wake with nothing else pickable ends, never falling through to it.
4. Low priority: *Map: an eval that measures what each approach is worth*, then the research issue on moving the semantic track to dbt v2.

Until the labels are renamed, read `autopilot-ready` as `agent:ready`, `needs-user` as `needs-owner`, and a `🤖 Autopilot handoff` or `🤖 Autopilot claim` comment as the skill's `🤖 Handoff` and claim.

## Gates

`cloud`: one gate stamp per head, whose one argv covers every gate the change calls for, the path-bound ones joined to the first line with `&&`; run it with `run_in_background`, once on the PR's final head; counts in the handoff:
`$R/scripts/gate_stamp.sh --pr <n> -- bash -c 'make tools && make check && make verify && <the path-bound gates>'`
- always: `make tools`, `make check` (`make lint` and `make test`, the alert rules' promtool tests included, with the Compose warehouse up and required), `make verify` (every image build; `BUILD_CA` passes the proxy's CA to the dependency steps)
- `dbt/**` changed: `make dbt-deps && (cd dbt && DBT_HOST=localhost DBT_PORT=5433 DBT_PROFILES_DIR=$PWD uvx --from dbt-core==1.12.6 --with dbt-postgres==1.11.0 dbt build)` (add `--with dbt-metricflow[dbt-postgres]==0.15.0` for `mf`), and `make gcp-image-check`
- `services/el-factory/**` changed: `make el-factory-up && make el-factory-down` (it waits for the service's health check against the Compose services)
- `platform/k8s/**`, `platform/kind/**` or a workload image changed: `make cluster-up && make workloads-up && make agent-deploy-check`; `agent-deploy-check` is a live model turn, so in `offline` such a change cannot complete its stamp on cloud and takes `needs-local-verify`
- `airflow/**` or `platform/helm/**` changed: `make cluster-up && make ci-integration`, and the exit checks the change touches, with `DAG_DELIVERY=local`
A PR whose full stamp cannot run in the session (a host the allowlist blocks, a gate that does not fit the session's disk) is never stamped with a subset: it takes `needs-local-verify`, its local checklist names the blocked gates and the full stamp command, and it waits for a local session to post that stamp before any review.

`local` (never in the cloud stamp; an agent on the owner's laptop runs them from the handoff's checklist, and the PR waits on `needs-local-verify`):
- git-sync delivery, when a change touches it: `make airflow-up` with the default `DAG_DELIVERY=git-sync` (the laptop's deploy key) — expect: the rollout Ready and `main`'s DAGs parsed.
- a WSL2-specific check: the command the handoff names — expect: its `passed` line.
A checklist that runs a DAG the PR changes deploys it with `DAG_DELIVERY=local make airflow-up`: git-sync serves `main`, so it would test the old DAG.

## Never

- Start or resume a paid or quota-bound eval pass (`make agent-eval`, `make record-call-labels`) except through the `experiment-preflight` skill, its limits those of the owner's go.
- Raise a GCP quota, spend cap or budget; run a live GCP step without `make gcp-cost-check` before and after, whose exit 1 (this month's cost at or above the tolerance) or 3 (not provable yet) ends the wake's GCP work with the SKU or the reason in the handoff; run an owner's step (`make gcp-up`, `gcp-down`, `gcp-workloads-up`): it is `needs-owner`.
- Dispatch a GitHub workflow: they run on demand only.
- Add to the frozen history (`PLAN.md`, `semantic/PLAN.md`, `LESSONS.md`, `LEDGER.md`, `ledger.d/`); a routine prompt asking for a fragment or a lessons line gets a `🤖` comment on its issue instead, listed under `Went wrong:` as `setup`.
- Pin an image tag by hand in the `Makefile`: `scripts/image-tag.sh` computes each tag from its build inputs.
- Change a choice the files describe without rewriting its present-tense reason in the same PR.

## Known conditions

- `docker build` steps reach PyPI through the TLS-intercepting proxy only with its CA: `make` passes it as the BuildKit secret `build_ca` when `BUILD_CA` (default `/root/.ccr/ca-bundle.crt`) exists, so build through `make`, never a plain `docker build`; seen 2026-10-30.
- A fresh session rebuilds every image: builds share a per-image layer cache at `ghcr.io/<owner>/<repo>/<image>:buildcache` (Makefile `BUILD_CACHE`, on by default on cloud; the `image-cache` skill); seen 2026-10-30.
- kind fails on the sandbox's cgroup v1 without `CAP_SYS_RESOURCE`: `cluster-up.sh` adapts the kubelet and containerd; seen 2026-10-30.
- kind nodes and pods cannot reach the internet through the host's loopback `HTTPS_PROXY`: `make egress-up` (run by `cluster-up` and every deploy target) relays the kind gateway to the proxy through the `kind-egress` container, gives containerd the proxy's CA, and sends docker.io pulls to mirror.gcr.io; seen 2026-10-31.
- `no space left on device` (the session's disk is about 39 GB): `make push` and `airflow-image` skip a tag the local registry serves and drop Docker's copy after a push (`FORCE_BUILD=1` rebuilds an unchanged one); run `docker builder prune -af` and remove old tags' images; seen 2026-10-31.
- `make tools` stops at kind's download and `make test` at the alert rules' promtool image, each on a `403`: `curl -sSI https://quay.io/v2/` answers `CONNECT tunnel failed, response 403`, so the environment's allowlist lacks `kind.sigs.k8s.io`, `get.helm.sh` and `quay.io`, which only the owner adds; until then no full stamp runs on cloud, so every PR takes `needs-local-verify` with those gates and the full stamp command in its checklist; seen 2026-11-14.
- Exporters publish no host port: read one with `docker run --rm --network pplk8s curlimages/curl …`; seen 2026-10-14.
