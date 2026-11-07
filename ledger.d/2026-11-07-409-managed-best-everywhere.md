## 2026-11-07 — Semantic track — Figure 1 compares MetricFlow with the managed best, like every other figure (#409)

- Done: `report/build.py` `make_parts` reads Figure 1's per-group gaps against the managed best, not the best Google setup in each group (owner, 2026-11-07: "#409 use managed best everywhere"); its header and titles say "the managed best" with the term's tooltip.
- Evidence: the frozen set's uncovered gap reads 33 points (80% against 47%), as Figure 4 shows, where it read 40 (87%, another setup); `tests/test_report_build.py` 24 passed, one new test pinning Figure 1's gaps to Figure 4's numbers; `tools/clipcheck.js --quick` 0 findings.
