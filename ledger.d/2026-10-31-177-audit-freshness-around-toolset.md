## 2026-10-31 — Semantic — the audit and the freshness survive the swap to DataAgentToolset

- Done: the semantic agent's audit and freshness move out of its metric toolset into one ADK `after_tool_callback` (`services/semantic-agent/src/semantic_agent/guard.py`), which audits every call to a tool the seam does not name as catalog-only and attaches the freshness of the metrics the result names (#177). `build_agent` takes a toolset and its catalog-only tools; `query_metrics` always names the metrics it ran; the eval reads a freshness statement from any data call. SL-4, SL-10 and the freshness lesson in `semantic/PLAN.md`, the agent README and `docs/semantic-layer-on-bigquery.md` say where both live after the swap.
- Evidence: see the PR.
- Decisions: SL-4 and SL-10 amended (freshness attached around the toolset; a data tool is every tool but the catalog-only ones).
- Open: whether `ask_data_agent`'s result names the metrics it used (`docs/semantic-layer-on-bigquery.md`, Unverified).
