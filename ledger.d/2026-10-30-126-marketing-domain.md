## 2026-10-30 — Semantic + Airflow — a marketing domain with its whole lineage

- Done: EL Factory serves a deterministic synthetic marketing source (campaigns, daily ad spend, CRM leads, bookings) under a `marketing` catalog pipeline; `marketing_elt` runs it, built with `sales_elt` by one ELT builder (`airflow/include/pplk8s/elt.py`); a `marketing` deadline (36 h); bronze → silver → gold (`marketing_daily`) → exposed (`channel_performance_daily`) models with tests; semantic models and eight metrics (spend, clicks, leads, bookings, booking value, cost per lead and per booking as ratios, a 30-day lead-to-booking conversion rate); fixture slice, parity in `semantic-check` and the emulator check, three eval questions (#126).
- Evidence: see the PR.
- Decisions: D38 and SL-8 (owner, 2026-10-30: the use case may add a domain's whole lineage, DAG included); `CLAUDE.md`'s two tracks amended to match.
- Fix after the first lab run (PR comment): on a fresh warehouse bookings named leads from before the extracted interval and failed `slv_bookings`' lead tests; those tests now warn, such a booking keeps a NULL campaign and gold counts it as channel `unknown` (owner: a lab warns, it need not be strict); the marketing readiness rows get a watermark (newest lead or booking).
- Open: a second lab run of `marketing_elt` on the cluster.
