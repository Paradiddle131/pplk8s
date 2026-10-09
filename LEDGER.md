# LEDGER

Append-only log of completed work, oldest first.
Add one entry at the end of every working session that changed the repo; never rewrite past entries, correct them with a new one.

Entry format:

```
## YYYY-MM-DD — <phase> — <one-line summary>
- Done: what changed (files/components).
- Evidence: the check that passed (command + observed result).
- Decisions: any PLAN.md decision added or changed, with its ID.
- Open: anything left unfinished or discovered, and where it is tracked.
```

## 2026-10-09 — Planning — initial plan, ledger, and agent instructions
- Done: wrote `PLAN.md` (goal, architecture, decisions D1–D12, phases 0–7), `LEDGER.md`, `CLAUDE.md`.
- Evidence: Airflow target verified against Cloud Composer release notes (Airflow 3 GA on Composer 3 since 2026-04-15; newest builds `composer-3-airflow-3.3.1` and `3.2.2` as of 2026-09-25) and the Airflow Helm chart release notes (1.22.0, 2026-06-01).
- Decisions: D1–D12 established.
- Open: Phase 7 (real GCP spend) parked pending user decision.
