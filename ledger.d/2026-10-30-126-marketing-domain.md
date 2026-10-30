## 2026-10-30 — Semantic + Airflow — a marketing domain with its whole lineage

- Done: EL Factory serves a deterministic synthetic marketing source (campaigns, daily ad spend, CRM leads, bookings) under a `marketing` catalog pipeline; `marketing_elt` runs it, built with `sales_elt` by one ELT builder (`airflow/include/pplk8s/elt.py`); a `marketing` deadline (36 h); bronze → silver → gold (`marketing_daily`) → exposed (`channel_performance_daily`) models with tests; semantic models and eight metrics (spend, clicks, leads, bookings, booking value, cost per lead and per booking as ratios, a 30-day lead-to-booking conversion rate); fixture slice, parity in `semantic-check` and the emulator check, three eval questions (#126).
- Evidence: see the PR.
- Decisions: D38 and SL-8 (owner, 2026-10-30: the use case may add a domain's whole lineage, DAG included); `CLAUDE.md`'s two tracks amended to match.
- Open: a live `marketing_elt` run on the cluster is for the local verify.
