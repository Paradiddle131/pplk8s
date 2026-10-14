## 2026-10-14 — Docs — README describes the platform, not its progress

- Done: rewrote `README.md` as a product README: one-line pitch, architecture and k9s screenshots (kept from the GitHub edit), design rules, a here-vs-GCP mapping, the four pipelines, the stack with pinned versions, prerequisites, quick start, checks, and layout. The phase status paragraph is gone; `PLAN.md` stays the tracker.
- Evidence: every version, DAG trigger, and `make` target in the README checked against `main` (`airflow/dags/`, `dbt/`, `Makefile`).
