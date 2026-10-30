## 2026-10-30 — Maintenance — cloud sessions are provisioned by claude-dotfiles alone

- Done: removed `docs/agents/cloud-setup.sh` and `docs/agents/cloud-docker.sh` (copies of claude-dotfiles' `bin/cloud-setup.sh` and its session-start hook, which the environment already runs) and `scripts/check-portable.sh` with its `make lint` step; the same guard now lives in claude-dotfiles (`bin/check-portable.sh`) and runs as this clone's pre-commit hook on cloud, set by its session-start hook in `.git/config`, so nothing in this repo carries it.
- Evidence: see the PR.
- Decisions: agent provisioning, rules, skills and guards belong to claude-dotfiles; this repo keeps only what is its own (`docs/agents/autopilot.md`, the `GITHUB_REPO` derivation).
- Open: none.
