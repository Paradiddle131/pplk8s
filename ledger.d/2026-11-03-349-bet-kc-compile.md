## 2026-11-03 — Semantic track — what Knowledge Catalog's compile_query and execute_query accept (#349)

- Done: `docs/research/semantic-bet/probes/349_kc_compile.py` (read-only: the two tools' schemas, `compile_query` over nine request shapes in two locations), the finding `docs/research/semantic-bet/findings/2026-11-03-349-kc-compile.md` with its raw output, the register's Q1 and Q3 rows, a daily retry in the watch.
- Evidence: 16 of 18 calls `An internal error has occurred`, a request with no `modelEntry` included; only a mistyped `rowLimit` gets a validation error; no doc page names either tool; Google's 2026-10-29 post makes semantic-model ingestion GA (dbt MetricFlow among six sources) and names no query API.
- Open: what the tools accept once their backend answers (the watch, #335).
