## 2026-10-31 — Maintenance — the autopilot skill comes from claude-dotfiles' plugin; a wake heals a missing setup

- Done: `docs/agents/autopilot.md` names the skill as `dotfiles:autopilot` (claude-dotfiles now ships its skills as plugins from its own marketplace, read in place, instead of links in `~/.claude/skills`) and tells a wake with no `~/.claude/cloud-target` to run claude-dotfiles' `bin/cloud-setup.sh pplk8s` first, which writes the Docker mirror, starts `dockerd` and installs the plugins.
- Evidence: see the PR.
- Decisions: none in this repo; provisioning stays in claude-dotfiles.
- Open: none.
