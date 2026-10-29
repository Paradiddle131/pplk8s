## 2026-10-29 — Agents — The v0 autopilot brief becomes a thin profile over the shared skill (claude-dotfiles#7, #13)

- Done: `docs/agents/autopilot.md` shrinks from 291 to 44 lines: the slots of the `autopilot` skill in claude-dotfiles (delivery per issue, never merge, queue = the semantic-layer map, cloud gates and laptop-only checks, never-list, known conditions). The run board, run feedback, heartbeat and claim sections move into the skill or go (claude-dotfiles `ways/lessons.md`). `CLAUDE.md` and `cloud-docker.sh` point at the profile.
- Evidence: a dry wake on cloud read only the skill and this profile, picked #100 (no blockers), and ran `claim.sh 100 --dry-run` and `file_issue.sh --epic 99 --dry-run` against this repo (printed writes only).
- Decisions: none in `PLAN.md`; the owner's 2026-10-29 review decided the pruning.
- Open: the label renames (`autopilot-ready` → `agent:ready`, `needs-user` → `needs-owner`) right after merge, and retiring this ledger under the placement rule (the adoption issue).
