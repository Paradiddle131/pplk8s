# Autopilot profile — pplk8s

Unattended cloud wakes on this repo follow the `dotfiles:autopilot` skill (claude-dotfiles' plugin; if missing, read `/home/user/claude-dotfiles/cloud/skills/autopilot/SKILL.md`) with the slots below.
A wake with no `~/.claude/cloud-target` (the environment's setup didn't run: no Docker mirror, `dockerd` stopped, the skill missing) first runs `bash /home/user/claude-dotfiles/bin/cloud-setup.sh pplk8s`.
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
3. The semantic track's next maps (owner's triage, 2026-10-31), each map's `autopilot-ready` sub-issues in its table's order: [Map #199: more domains](../../../../issues/199), then [Map #197: the questions business users ask](../../../../issues/197), [Map #200: one governed semantic layer for every agent](../../../../issues/200).
4. [Map #212: the semantic track on a free-tier GCP project](../../../../issues/212) (unparked by the owner, 2026-11-01), under `semantic/PLAN.md` SL-13 and `platform/gcp/README.md`: never raise a quota, a spend cap or the budget; `make gcp-cost-check` before and after every live step, its exit 1 (a cost) or 3 (not provable yet) ending the wake's GCP work with the SKU or the reason in the handoff; `make gcp-up` is a `needs-owner` step.
5. Low priority: [Map #198: the eval](../../../../issues/198), then [#202](../../../../issues/202) (dbt v2 research).

Until the labels are renamed, read `autopilot-ready` as `agent:ready`, `needs-user` as `needs-owner`, and a `🤖 Autopilot handoff` or `🤖 Autopilot claim` comment as the skill's `🤖 Handoff` and claim.

## Gates

Cloud runs, with their counts in the handoff:
- `make tools` first in each session: `make lint` runs `make gcp-validate`, which needs the pinned OpenTofu and tflint
- `make check` (`make lint` and `make test` with the Compose warehouse up and required; GitHub Actions is off, PLAN.md D26, so a PR shows no checks)
- dbt from the host when `dbt/**` changed: `cd dbt && DBT_HOST=localhost DBT_PORT=5433 DBT_PROFILES_DIR=$PWD uvx --from dbt-core==1.12.6 --with dbt-postgres==1.11.0 dbt …` (add `--with dbt-metricflow[dbt-postgres]==0.15.0` for `mf`)
- EL Factory from the host when `services/el-factory/**` changed: `uv run gunicorn` with the env from `scripts/el-factory-local.sh`
- alert rules: Prometheus `quay.io/prometheus/prometheus:v3.15.0` on `--network pplk8s` with the rule file, as `tests/monitoring/rules-test.sh` does
- `make verify` (every image build; `BUILD_CA` passes the proxy's CA to the dependency steps)
- the cluster when `platform/k8s/**`, `platform/kind/**` or a workload image changed: `make tools`, `make cluster-up`, `make workloads-up`, and `make agent-deploy-check` for the semantic agent

- Airflow when `airflow/**` or `platform/helm/**` changed: `make ci-integration`, and the phase checks the change touches, with `DAG_DELIVERY=local` (git-sync needs the laptop's deploy key)

Left to the laptop (the handoff's local checklist): git-sync delivery and anything WSL2-specific; a check that does not fit the session's disk (below) says so in the handoff.
A checklist that runs a DAG the PR changes deploys it with `DAG_DELIVERY=local make airflow-up`: the default git-sync serves `main`, so the run would test the old DAG (seen on #113).

## Never

- Dispatch a workflow (`ci.yaml` or `integration.yaml`; on-demand only, PLAN.md D26).
- Edit `LEDGER.md`: add the entry as `ledger.d/<YYYY-MM-DD>-<n>-<slug>.md` in the PR.
- Change an image's contents without bumping its tag in the `Makefile` (D16): a Dockerfile, dependencies, dbt models, service code, `airflow/include/**`.
- Change a `PLAN.md` decision without its row in the same PR.

## Known conditions

- `docker build` steps reach PyPI through the TLS-intercepting proxy only with its CA: `make` passes it as the BuildKit secret `build_ca` when `BUILD_CA` (default `/root/.ccr/ca-bundle.crt`) exists; a plain `docker build` still fails TLS; seen 2026-10-30.
- Builds read and write a per-image layer cache at `ghcr.io/<owner>/<repo>/<image>:buildcache` (Makefile `BUILD_CACHE`, on by default on cloud; the `image-cache` skill), so a fresh session rebuilds only what changed; seen 2026-10-30.
- kind runs on the sandbox's cgroup v1 without `CAP_SYS_RESOURCE` because `cluster-up.sh` adapts the kubelet and containerd; seen 2026-10-30.
- The nodes and pods reach the internet through `platform/kind/egress-up.sh` (`make egress-up`, run by `cluster-up` and every deploy target): kind copies the host's loopback `HTTPS_PROXY` into the nodes, where it names the node itself, so a relay container `kind-egress` on the kind gateway pipes to the proxy, containerd uses it with the proxy's CA, and docker.io pulls go to mirror.gcr.io (#119); seen 2026-10-31.
- The session's disk allowance (about 39 GB) holds the whole lab only without duplicates: on cloud `make push` and `airflow-image` skip a tag the local registry already serves (so an image change needs its tag bump, or `FORCE_BUILD=1`) and drop Docker's copy and BuildKit's cache after a push (Makefile `publish`); on `no space left on device`, `docker builder prune -af` and remove images of old tags (#119); seen 2026-10-31.
- A session can start without the cloud setup: no `~/.claude/settings.json` or `/etc/docker/daemon.json`, `dockerd` stopped, and uv warns `UV_NATIVE_TLS is deprecated`; Compose pulls then hit Docker Hub's 429. Write the mirror `daemon.json` (claude-dotfiles `bin/cloud-setup.sh` step 5) and start `dockerd` as `cloud/hooks/session-start.sh` does; seen 2026-10-31 (seven times); fix: claude-dotfiles issue 28.
- Exporters publish no host port: read one with `docker run --rm --network pplk8s curlimages/curl …`; seen 2026-10-14.
