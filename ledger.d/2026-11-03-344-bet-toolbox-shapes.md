## 2026-11-03 — Semantic track — generated Toolbox tools over the bet's table functions, and the frozen set's fit to their shapes (#344)

- Done: `docs/research/semantic-bet/probes/330_toolbox_tools.py` (the seven table functions into Toolbox 1.x's flat `330_tools.yaml`, `useClientOAuth`), `330_toolbox_check.sh` (Toolbox 1.1.0 with no network, over MCP stdio), `330_shape_coverage.py` (a hand verdict per frozen case), the finding `docs/research/semantic-bet/findings/2026-11-03-344-toolbox-shapes.md`, the register's Q5 row.
- Evidence: Toolbox 1.1.0 serves the 7 tools offline and refuses a stdio call for want of an `Authorization` header; the seven tools answer 26 of 96 cases exactly and 12 through the agent's arithmetic; one tool per metric would answer 46 exactly but drop every case needing a dimension; the two together reach 57.
- Open: the live part (the statements on BigQuery, an ADK agent on Toolbox over HTTP) stays #330's, after #329's live part and #338.
