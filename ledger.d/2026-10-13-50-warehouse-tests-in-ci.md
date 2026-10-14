## 2026-10-13 — CI — warehouse-backed tests run in CI (#50)

- Done: `ci.yaml`'s `test` job starts the Compose warehouse and sets `PPLK8S_REQUIRE_WAREHOUSE=1`; the readiness and file-ledger fixtures fail there instead of skipping (PR #51).
- Evidence: CI `test` log `119 passed` (was 117 passed, 2 skipped); without a warehouse and with the variable, the 2 tests error.
- Decisions: D26 amended.
- Open: #18 (PR #31), #25, #42.
- Note: folded late (2026-10-14, #83); the cloud handoff's paste-at-merge step lost it, which is why `ledger.d/` exists.
