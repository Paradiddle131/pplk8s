## 2026-11-01 — Semantic track — the recruitment snapshot replayed extract by extract on the BigQuery emulator

- Done: `bigquery-emulator-check` now replays the five recruitment extracts one at a time with a build after each, on a recreated emulator, and asserts the 15-row stage history `semantic-check` asserts on Postgres, the seven recruitment hops and 2 candidates in interview on 3 October. The emulator's `DROP TABLE` panic (`googlesqlite: slice bounds out of range [-2147...:]`) is not tied to the statement: the stack shows the engine rebuilding its catalog through go-googlesql's WASM module, the emulator held about 5 GiB after the full build, and the same replay on a fresh emulator never panics. No release newer than `0.8.1` exists, so the pin stays and the shim is unchanged.
- Evidence: in the PR (the emulator check before and after, `make check`).
- Decisions: semantic/PLAN.md SL-17 (the emulator sentence).
