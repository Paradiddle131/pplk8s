## 2026-11-06 — Semantic track — MetricFlow with arithmetic, and report revision 3 (#400, #396, #401)

- Done: `custom-metricflow-compute` and `cc-metricflow-compute` (RULE.md § Changes since freezing, 2026-11-06T21:57Z): `custom-metricflow`'s agent and tools with an instruction allowing sums, differences, ratios and shares of `query_metrics` results, as Google's agents compute in their SQL (the governed agent's own instruction says "select, filter and add up"); the old setups keep every run; the free lane asks the ADK setup from tonight.
- Done: strict Claude Code passes of `cc-metricflow-compute`: Haiku and Sonnet at k = 3 on every set, Opus 50 runs on the extended hard set; there Haiku 75%, Sonnet 72%, Opus 74% right (`cc-metricflow`: 64%, 52%, 42%), so the model inversion was the instruction.
- Done: the page has design A's tab strip (titles only), a glossary table grouped by type with search and filter, tooltips with labelled sections, and an impeccable-detector pass on the text-heavy parts (`report/NOTES.md`, Revision 3).
- Evidence: `test_bet_tools.py` and `test_report_build.py` pass (8); `tools/clipcheck.js --quick`, now tab-aware, 0 findings; page version 28 and #336's artifact 4 with the same SHA-256.
- Open: the owner's call on #400's headline (which MetricFlow setup the page's "MetricFlow on the free model" reads once the free model has run it).
