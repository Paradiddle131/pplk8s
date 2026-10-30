#!/bin/bash
# Cloud environment setup for pplk8s-worker routine runs (docs/agents/autopilot.md).
# The environment's Setup script should only call this file, so it versions with the code:
#   bash /home/user/pplk8s/docs/agents/cloud-setup.sh  # cloud-setup v2
# It runs as root after the repos are cloned and before Claude Code starts. Its result is
# cached as a file snapshot for ~7 days when it finishes within ~5 minutes, so keep it lean
# and link into the clones instead of copying (a copy would go stale with the cache).
# Only an edit of the environment's Setup field (or the ~7-day expiry) re-runs this script;
# a change to this file alone never reaches the runs. So on every change here, bump the
# version comment above and in the environment's Setup field (the user does that).
# Repo dependencies (uv sync, images) are the agent's job, not this script's.
set -u

# 1. Find the clones; the routine attaches pplk8s and claude-dotfiles.
find_clone() {
  find /home/user /root /workspace -maxdepth 3 -type d -name "$1" 2>/dev/null |
    while read -r d; do [ -d "$d/.git" ] && echo "$d" && break; done
}
PPLK8S=$(find_clone pplk8s)
DOTFILES=$(find_clone "${DOTFILES_REPO:-claude-dotfiles}")
echo "pplk8s: ${PPLK8S:-MISSING}  claude-dotfiles: ${DOTFILES:-MISSING}"

# 2. The user's skills, linked from the dotfiles clone (local-only skills are left out:
#    laptop-only memory, artifact and design tooling, and localhost services do not exist on cloud).
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

# 4. The standing rules for cloud: claude-dotfiles' cloud/CLAUDE.md,
#    symlinked so each session reads the fresh clone's version, never a cached copy.
if [ -n "$DOTFILES" ] && [ -f "$DOTFILES/cloud/CLAUDE.md" ]; then
  ln -sfn "$DOTFILES/cloud/CLAUDE.md" ~/.claude/CLAUDE.md
  echo "standing rules: linked $DOTFILES/cloud/CLAUDE.md"
else
  printf '%s\n' "- Unattended run: follow docs/agents/autopilot.md in the target repo." >~/.claude/CLAUDE.md
  echo "standing rules: cloud/CLAUDE.md missing in claude-dotfiles; wrote a one-line fallback"
fi

# 5. Git identity for commits made by the agent.
owner=$(git -C "${PPLK8S:-.}" remote get-url origin 2>/dev/null | sed -E 's#^(git@|[a-z]+://)([^@/]*@)?github\.com[:/]##; s#/.*##')
git config --global user.name >/dev/null || git config --global user.name "$owner"
git config --global user.email >/dev/null || git config --global user.email "$owner@users.noreply.github.com"

# 6. Docker: start the daemon with a registry mirror (the snapshot keeps no processes, so
#    runs call this again; see the script).
[ -n "$PPLK8S" ] && bash "$PPLK8S/docs/agents/cloud-docker.sh"

# 7. Quick capability report for the run board (the agent reads it from the setup log).
command -v docker >/dev/null && docker info >/dev/null 2>&1 && echo "docker: ok" || echo "docker: unavailable"
command -v uv >/dev/null && echo "uv: ok" || echo "uv: missing (the agent installs it: pip install uv)"

echo "pplk8s-worker setup: done"
