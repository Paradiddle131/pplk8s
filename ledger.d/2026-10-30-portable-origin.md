## 2026-10-30 — Maintenance — the repo names its GitHub owner only through the origin remote

- Done: the Makefile derives `GITHUB_REPO` (`<owner>/<repo>`) from the origin remote; `BUILD_CACHE` and Airflow's git-sync repo (`deploy.sh` sets `dags.gitSync.repo`) come from it, and `docs/agents/cloud-setup.sh` derives its fallback git identity the same way. Links to this repo's issues are relative (`../../issues/N`). `scripts/check-portable.sh` (in `make lint`) fails on the owner's login in any tracked file but `LEDGER.md` and `ledger.d/`.
- Evidence: see the PR.
- Decisions: derive rather than parametrize by hand, so a fork builds, caches, syncs and links against itself with no edit; history files keep their literal facts.
- Open: none.
