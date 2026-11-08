## 2026-11-08 — Maintenance — the platform and semantic-agent sheets show the Cloud SQL and MCP marks (#421)

- Done: `assets/platform.html` marks the metadata DB with Cloud SQL's logo in its gcp view, `assets/semantic-agent.html` marks `mcp_server.py` with MCP's (its card 32 wider so the logo clears its line); both rebuilt with the `draw-architecture` kit that adds those marks to its registry, and their PNGs re-exported.
- Evidence: in the PR (`bin/check.cjs` on both sheets).
- Decisions: none.
- Open: both sheets still lack a headline, which #317 adds (#315).
