# Autopilot profile — pplk8s

Unattended cloud wakes on this repo follow the `autopilot` skill (`~/.claude/skills/autopilot/SKILL.md`; if missing, read `/home/user/claude-dotfiles/cloud/skills/autopilot/SKILL.md`) with the slots below.
The routine prompt: "Follow `docs/agents/autopilot.md` in pplk8s and do one wake."
Standing permission (owner, 2026-10-13): push `claude/*` branches, open and edit PRs and issues, comment, label, mark PRs ready, without asking.

## Delivery

`per-issue`: branch `claude/<n>-<slug>`, one draft PR per issue; stack on an open PR's branch when the issue depends on it.

## Digest

The body of [#43](../../../../issues/43) lists open owner questions only; PRs waiting for the laptop are the `needs-local-verify` label, so drop any other section of that body when you next edit it.

## Merge policy

Never merge (owner, 2026-10-12): the real exit checks need the laptop's kind cluster.
A finished, cloud-verified PR is marked ready and labelled `needs-local-verify`; the owner's local session runs its checklist and merges.

## Queue

1. [Map #135: an agent-ready BigQuery warehouse](../../../../issues/135): its `autopilot-ready` sub-issues in order; design in `semantic/PLAN.md`.
2. `agent:ready` issues labelled `bug`, then `lesson` (a Stage 2/3 lesson researched from primary sources, as a docs-only PR).

Until the labels are renamed, read `autopilot-ready` as `agent:ready`, `needs-user` as `needs-owner`, and a `🤖 Autopilot handoff` or `🤖 Autopilot claim` comment as the skill's `🤖 Handoff` and claim.

## Gates

Cloud runs, with their counts in the handoff:
- `make check` (`make lint` and `make test` with the Compose warehouse up and required; GitHub Actions is off, PLAN.md D26, so a PR shows no checks)
- dbt from the host when `dbt/**` changed: `cd dbt && DBT_HOST=localhost DBT_PORT=5433 DBT_PROFILES_DIR=$PWD uvx --from dbt-core==1.12.6 --with dbt-postgres==1.11.0 dbt …` (add `--with dbt-metricflow[dbt-postgres]==0.15.0` for `mf`)
- EL Factory from the host when `services/el-factory/**` changed: `uv run gunicorn` with the env from `scripts/el-factory-local.sh`
- alert rules: Prometheus `quay.io/prometheus/prometheus:v3.15.0` on `--network pplk8s` with the rule file, as `tests/monitoring/rules-test.sh` does
- `make verify` (every image build; `BUILD_CA` passes the proxy's CA to the dependency steps)
- the cluster when `platform/k8s/**`, `platform/kind/**` or a workload image changed: `make tools`, `make cluster-up`, `make workloads-up`, and `make agent-deploy-check` for the semantic agent

Left to the laptop (the handoff's local checklist): `make ci-integration` and the phase checks that deploy Airflow or monitoring, whose images the kind nodes cannot pull on cloud (#119).
A checklist that runs a DAG the PR changes deploys it with `DAG_DELIVERY=local make airflow-up`: the default git-sync serves `main`, so the run would test the old DAG (seen on #113).

## Never

- Dispatch a workflow (`ci.yaml` or `integration.yaml`; on-demand only, PLAN.md D26).
- Edit `LEDGER.md`: add the entry as `ledger.d/<YYYY-MM-DD>-<n>-<slug>.md` in the PR.
- Change an image's contents without bumping its tag in the `Makefile` (D16): a Dockerfile, dependencies, dbt models, service code, `airflow/include/**`.
- Change a `PLAN.md` decision without its row in the same PR.

## Known conditions

- `docker build` steps reach PyPI through the TLS-intercepting proxy only with its CA: `make` passes it as the BuildKit secret `build_ca` when `BUILD_CA` (default `/root/.ccr/ca-bundle.crt`) exists; a plain `docker build` still fails TLS; seen 2026-10-30.
- Builds read and write a per-image layer cache at `ghcr.io/<owner>/<repo>/<image>:buildcache` (Makefile `BUILD_CACHE`, on by default on cloud; the `image-cache` skill), so a fresh session rebuilds only what changed; seen 2026-10-30.
- kind runs on the sandbox's cgroup v1 without `CAP_SYS_RESOURCE` because `cluster-up.sh` adapts the kubelet and containerd; its nodes cannot pull from the internet, so only images in the local registry run (#119); seen 2026-10-30.
- Exporters publish no host port: read one with `docker run --rm --network pplk8s curlimages/curl …`; seen 2026-10-14.
