## 2026-10-14 — Phase 8 — the warehouse ceiling rises from 15 GB to 20 GB (#87)

- Done: D35's warehouse ceiling is 20 GB; `phase8-check` fails above it instead of above 15 GB.
- Evidence: #87 measured ≈ 2.6 GB per yellow month all-in, so D35's steady state of 6 yellow months (latest 3 + 3 drift months) projects to ≈ 15.6 GB once 2026-09 publishes; the lab is at 13 GB with 5. `make lint`; `phase8-check` not re-run for a constant change.
- Decisions: D35 amended. The user chose a bigger ceiling over dropping the 2026-06 drift month ("size is not an issue"); 20 GB rather than ~17 GB also covers a 7th month a concurrent catch-up run holds until the next run retires it.
- Open: none.
