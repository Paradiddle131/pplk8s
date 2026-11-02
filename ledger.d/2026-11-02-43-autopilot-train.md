## 2026-11-02 — Autopilot — one train, steered from the digest (#43)

- Done: `docs/agents/autopilot.md`: Delivery is `train claude/autopilot-train`, an image tag bumps once per train, #43's `Mode` and `Owner lane` lines pause a wake or keep it off the owner's attended work, and the merge policy names the train.
- Evidence: one night of per-issue wakes left seven PRs, two stacks, four parallel image-tag bumps and one silent collision (two PRs took `semantic-agent:0.1.39`; git merged the second without a conflict); `make lint` passed.
- Decisions: none in PLAN.md; the profile has had no `local` gates since 2026-11-01, the case claude-dotfiles' lessons give for a train.
- Open: none.
