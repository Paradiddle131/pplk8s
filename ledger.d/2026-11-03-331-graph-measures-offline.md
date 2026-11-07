## 2026-11-03 — Semantic track — which metrics compile to graph measures, offline (#331, first part)

- Done: `docs/research/semantic-bet/probes/331_graph_measures.py` classifies every metric under BigQuery's graph-measure rules and writes `probes/331_bet_graph.sql` (`bet_graph.metrics`: 12 node and 11 edge tables); the finding `docs/research/semantic-bet/findings/2026-11-03-331-graph-measures.md`; Q6 is `measuring`.
- Evidence: 30 of 57 metrics compile (simple 26/33, ratio 4/10, derived, cumulative and conversion 0), 35 at most with a composite key and filtered helper measures; the dropped set matches Lightdash's.
- Open: the dry run and the data agent with the graph, live after #338.
