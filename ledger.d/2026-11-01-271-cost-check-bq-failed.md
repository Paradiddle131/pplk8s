## 2026-11-01 — Semantic — `make gcp-cost-check` names a failing `bq` instead of blaming the export's lag (#271)

- Done: `platform/gcp/cost-check.sh` keeps `bq ls`'s exit status and output: "Not found: Dataset" (on stdout, where bq prints its errors) is still the no-export case, and any other failure exits 3 as `UNKNOWN: bq failed: <bq's last lines>`, so a broken install or a missing credential no longer reads as "no export table yet".
- Done: `platform/gcp/tests/test_cost_check.py` runs the script against a fake `bq` for each answer (a crash, an error, a missing dataset, no export table, $0.00, a cost, a failed query); it runs in `make gcp-validate`.
- Evidence: see the PR; the two new failure cases fail on the old script and pass on the new.
- Decisions: none.
- Open: none.
