## 2026-11-07 — Maintenance — cloud sessions are provisioned by loadout

- Done: `CLAUDE.md`, `docs/agents/autopilot.md`, `platform/gcp/README.md` and the two asset sheets' comments name loadout, the public successor of the agent-setup repo: the skill is `cloud:autopilot`, the setup `cloud/setup.sh pplk8s`, the commit guard `cloud/githooks/check-portable.sh`.
- Evidence: `git grep` finds no other reference outside the ledger; the environment's Setup line runs loadout's setup when it is cloned and the old one otherwise, so sessions keep working in either state.
- Decisions: none in this repo; provisioning stays outside it.
