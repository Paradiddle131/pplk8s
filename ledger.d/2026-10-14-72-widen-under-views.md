## 2026-10-14 — Phase 8 — EL Factory widens landed columns under bronze views (#72)

- Done: EL Factory drops and recreates the views over a landing table around a column widening, in one transaction; the views keep their column types (`services/el-factory/src/el_factory/warehouse.py`). `ELF_IMAGE` 0.5.1. Built on a cloud run (PR #81).
- Evidence: cloud: the new warehouse-backed test red on `main`, green here; real yellow 2023-01 after 2026-08 under the bronze views: `main` HTTP 500 `cannot alter type of a column used by a view or rule`, fixed 3,066,766 rows, `dbt build tag:tlc` 2023-01 PASS=20. Local `make verify` 2026-10-14: lint clean, airflow 158, el-factory 102 (incl. `test_widening_keeps_the_views_that_read_the_landing_table`, no skips), event-adapter 32, every image built (el-factory 0.5.1).
- Found: only 2023-01 of the 2023 files has the old schema (#82, settled: D35's drift month is 2023-01).
- Open: #58 (PR #80, stacked on this).
