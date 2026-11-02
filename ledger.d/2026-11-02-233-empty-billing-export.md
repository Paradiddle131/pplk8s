## 2026-11-02 — GCP — an empty billing export no longer passes as $0.00

- Done: `platform/gcp/cost-check.sh` exits 3 (unknown) when the export has no rows for the project this month, instead of printing `ok … $0.00`; a test covers it; claude-dotfiles' session-start `status.sh` got the same fix in its own PR.
- Evidence: on 2026-11-02 11:33Z the export table (created 2026-10-31 23:36Z) held 0 rows while BigQuery had billed about 16.8 GB on 2026-11-01, and `make gcp-cost-check` still exited 0; it now exits 3 with `UNKNOWN: no billing export rows for pplk8s-lab-001 this month yet`.
- Decisions: no rows this month means unknown, so live GCP work waits for the export's first rows (owner, 2026-11-02).
- Open: if the export is still empty around 2026-11-03 12:00Z, check its settings in the Cloud console (Billing → Billing export).
