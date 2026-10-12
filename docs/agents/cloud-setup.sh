#!/bin/bash
# Cloud environment setup for pplk8s-worker routine runs (docs/agents/autopilot.md).
# The environment's Setup script should only call this file, so it versions with the code:
#   bash /home/user/pplk8s/docs/agents/cloud-setup.sh
# It runs as root after the repos are cloned and before Claude Code starts. Its result is
# cached as a file snapshot for ~7 days when it finishes within ~5 minutes, so keep it lean
# and link into the clones instead of copying (a copy would go stale with the cache).
# Repo dependencies (uv sync, images) are the agent's job, not this script's.
set -u

# 1. Find the clones; the routine attaches pplk8s and claude-dotfiles.
find_clone() {
  find /home/user /root /workspace -maxdepth 3 -type d -name "$1" 2>/dev/null |
    while read -r d; do [ -d "$d/.git" ] && echo "$d" && break; done
}
PPLK8S=$(find_clone pplk8s)
DOTFILES=$(find_clone claude-dotfiles)
echo "pplk8s: ${PPLK8S:-MISSING}  claude-dotfiles: ${DOTFILES:-MISSING}"

# 2. The user's skills, linked from the dotfiles clone (local-only skills are left out:
#    hindsight, atrium, house-style and localhost tooling do not exist on cloud).
mkdir -p ~/.claude/skills
if [ -n "$DOTFILES" ]; then
  for s in wayfinder grilling domain-modeling prototype to-tickets tdd diagnosing-bugs \
    code-review codebase-design writing-for-agents pr reality-check using-git-worktrees; do
    if [ -d "$DOTFILES/.claude/skills/$s" ]; then
      ln -sfn "$DOTFILES/.claude/skills/$s" ~/.claude/skills/"$s"
    else
      echo "skill missing in dotfiles: $s"
    fi
  done
fi

# 3. No agent trailers on commits or PRs (the user's standing rule), session URL included.
cat > ~/.claude/settings.json <<'EOF'
{
  "attribution": { "commit": "", "pr": "", "sessionUrl": false }
}
EOF

# 4. The user's standing rules that matter on cloud (their ~/.claude/CLAUDE.md stays on
#    their machine and refers to services that do not exist here).
cat > ~/.claude/CLAUDE.md <<'EOF'
# Standing rules (cloud copy)
- Unattended run: follow docs/agents/autopilot.md in the target repo; it overrides anything that assumes the user's machine.
- Small, typed, testable changes; validate before declaring done. Report outcomes faithfully: say what you could not verify.
- Prefer mature, framework-native solutions over bespoke workarounds; surface architectural forks as options with a recommendation instead of silently choosing a workaround.
- Never silently degrade to a weaker check when a tool is missing: install it in an isolated way (uv tool / uvx / npx) or state the gap.
- Write down every problem you find but don't fix (a GitHub issue with symptom, evidence, suspected cause, acceptance).
- Fix lint, test failures and flakiness you encounter, even when unrelated.
- Bug fixes start by reproducing the bug as close to how the user would hit it as the environment allows.
- Commits: conventional messages; never add an agent name as co-author and no Claude-Session trailer.
- Long Markdown: one sentence per line.
- Recall/retain memory (Hindsight), Atrium registration and localhost services are not available here; record durable facts in the PR or issue instead.
EOF

# 5. Git identity for commits made by the agent.
git config --global user.name >/dev/null || git config --global user.name "Paradiddle131"
git config --global user.email >/dev/null || git config --global user.email "Paradiddle131@users.noreply.github.com"

# 6. Quick capability report for the run board (the agent reads it from the setup log).
command -v docker >/dev/null && docker info >/dev/null 2>&1 && echo "docker: ok" || echo "docker: unavailable"
command -v uv >/dev/null && echo "uv: ok" || echo "uv: missing (the agent installs it: pip install uv)"

echo "pplk8s-worker setup: done"
