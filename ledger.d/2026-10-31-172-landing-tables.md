## 2026-10-31 — Maintenance — every extract and load re-creates all landing tables, so sales_elt passes on a fresh warehouse

- Done: EL Factory ensures every `ds_source` landing table before each extract or load, not only the requested one (#172): after `make services-reset` under a running EL Factory, a sales extract left `ds_source.open_meteo_hourly_weather` missing and `sales_elt`'s `dbt_bronze` failed, because the weather models are tagged `sales` (D20) while no DAG extracts weather. el-factory 0.7.2.
- Evidence: see the PR.
- Decisions: none; D20 stands (the weather models stay in `sales` until a weather DAG exists).
- Open: none.
