# Autopilot profile — pplk8s

Unattended cloud wakes on this repo follow the `autopilot` skill (`~/.claude/skills/autopilot/SKILL.md`; if missing, read `/home/user/claude-dotfiles/cloud/skills/autopilot/SKILL.md`) with the slots below.
The routine prompt: "Follow `docs/agents/autopilot.md` in pplk8s and do one wake."
Standing permission (owner, 2026-10-13): push `claude/*` branches, open and edit PRs and issues, comment, label, mark PRs ready, without asking.

## Delivery

`per-issue`: branch `claude/<n>-<slug>`, one draft PR per issue; stack on an open PR's branch when the issue depends on it.
Digest of open owner questions: the body of [#43](https://github.com/Paradiddle131/pplk8s/issues/43), one line each, removed when answered.

## Merge policy

Never merge (owner, 2026-10-12): the real exit checks need the laptop's kind cluster.
A finished, cloud-verified PR is marked ready and labelled `needs-local-verify`; the owner's local session runs its checklist and merges.

## Queue

1. [Map #99: dbt semantic layer and a metrics agent](https://github.com/Paradiddle131/pplk8s/issues/99): its sub-issues in order; design in `semantic/PLAN.md`.
2. Open `bug` issues, then `lesson` issues (a Stage 2/3 lesson researched from primary sources, as a docs-only PR).

## Gates

Cloud runs, with their counts in the handoff:
- `make lint`
- `make services-up`, then `PPLK8S_REQUIRE_WAREHOUSE=1 make test` (stands in for CI's `test` job)
- dbt from the host when `dbt/**` changed: `cd dbt && DBT_HOST=localhost DBT_PORT=5433 DBT_PROFILES_DIR=$PWD uvx --from dbt-core==1.12.5 --with dbt-postgres==1.11.0 dbt …` (add `--with dbt-metricflow[dbt-postgres]==0.15.0` for `mf`)
- EL Factory from the host when `services/el-factory/**` changed: `uv run gunicorn` with the env from `scripts/el-factory-local.sh`
- alert rules: Prometheus `quay.io/prometheus/prometheus:v3.15.0` on `--network pplk8s` with the rule file, as `tests/monitoring/rules-test.sh` does

Left to the laptop (the handoff's local checklist): `make verify` (image builds), `make ci-integration` and the phase checks (kind).

## Never

- Dispatch `integration.yaml` or the `images` job (on-demand only, PLAN.md D26).
- Edit `LEDGER.md`: add the entry as `ledger.d/<YYYY-MM-DD>-<n>-<slug>.md` in the PR.
- Change an image's contents without bumping its tag in the `Makefile` (D16): a Dockerfile, dependencies, dbt models, service code, `airflow/include/**`.
- Change a `PLAN.md` decision without its row in the same PR.

## Known conditions

- `docker build` steps that `pip install` fail TLS, so `make build`, `make verify` and `make phase1-check` don't run on cloud: use the host-side gates above; seen 2026-10-12.
- Run Docker first with `bash docs/agents/cloud-docker.sh` when `docker info` fails (this repo's setup script predates the shared one); seen 2026-10-13.
- Exporters publish no host port: read one with `docker run --rm --network pplk8s curlimages/curl …`; seen 2026-10-14.
