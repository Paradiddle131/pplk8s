# LEDGER

Append-only log of completed work, oldest first.
Add one entry at the end of every working session that changed the repo; never rewrite past entries, correct them with a new one.

Entry format:

```
## YYYY-MM-DD — <phase> — <one-line summary>
- Done: what changed (files/components).
- Evidence: the check that passed (command + observed result).
- Decisions: any PLAN.md decision added or changed, with its ID.
- Open: anything left unfinished or discovered, and where it is tracked.
```

## 2026-10-09 — Planning — initial plan, ledger, and agent instructions
- Done: wrote `PLAN.md` (goal, architecture, decisions D1–D12, phases 0–7), `LEDGER.md`, `CLAUDE.md`.
- Evidence: Airflow target verified against Cloud Composer release notes (Airflow 3 GA on Composer 3 since 2026-04-15; newest builds `composer-3-airflow-3.3.1` and `3.2.2` as of 2026-09-25) and the Airflow Helm chart release notes (1.22.0, 2026-06-01).
- Decisions: D1–D12 established.
- Open: Phase 7 (real GCP spend) parked pending user decision.

## 2026-10-09 — Phase 0 — toolchain, skeleton, kind cluster with local registry
- Done: `scripts/install-tools.sh` (checksum-pinned kind v0.33.0, helm v3.22.0, k9s v0.51.0 into `~/.local/bin`); `platform/kind/` (cluster config, `cluster-up.sh`, `cluster-down.sh`, `cluster-check.sh`); `Makefile` (`tools`, `lint`, `cluster-up/down/check`); target directory layout; `.gitignore`; README prerequisites.
- Evidence: Docker Desktop 29.5.3 via WSL integration, 28 CPUs / 31 GiB visible. `make cluster-up` → 3 nodes Ready on v1.36.4 in ~60 s; `make cluster-check` → 2 Ready workers, busybox pushed to `localhost:5001` and run as a pod in-cluster; `make cluster-down` → no clusters, no leftover containers; down/up/check cycle repeated cleanly; `make lint` (shellcheck) clean.
- Decisions: D4 refined with the concrete pins (Kubernetes 1.36.4 = GKE Regular default, registry `registry:3` on `localhost:5001`).
- Open: none. Fixed during the session: workers were not yet Ready right after `kind create --wait` (it waits only for the control plane); `cluster-up.sh` now waits for all nodes.
