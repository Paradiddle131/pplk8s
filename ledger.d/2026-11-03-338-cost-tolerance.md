## 2026-11-03 — Semantic track — the cost check accepts incidental charges under $1.00 a month (#338)

- Done: `platform/gcp/cost-check.sh` passes a month's total after credits under `GCP_COST_TOLERANCE_USD` (default 1.00) and lists each costly SKU, fails at or above it, and refuses a malformed tolerance (exit 3); `0` keeps the strict rule; five new cases in `platform/gcp/tests/test_cost_check.py`; the rule in `platform/gcp/README.md`, `CLAUDE.md`, the Makefile's help and SL-13.
- Evidence: the owner's answer to #338 (2026-11-03: "accept things like $0.000010 Artifact Registry charge under a dollar"); `make gcp-cost-check` on the lab project's export (until 2026-11-03T01:12Z) now exits 0 and lists the $0.000010 Artifact Registry egress line, exit 1 with `GCP_COST_TOLERANCE_USD=0`; `platform/gcp/tests` 82 passed.
- Open: #338's other half, where the intercontinental registry traffic came from and moving pushes inside North America.
