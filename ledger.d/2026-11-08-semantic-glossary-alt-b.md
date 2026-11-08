## 2026-11-08 — Semantic track — the glossary as a compact list that opens in place (design B)

- Done: one of three designs for the owner to compare: each glossary entry is one row, its term (a disclosure button) beside its one-sentence meaning, its labelled longer lines folded under it with `hidden="until-found"`; a press on the row opens it in place, many rows may be open, a search narrows the rows and opens nothing, a link or a hash opens its entry.
- Done: the type chips stay the kit's filters with their counts; a row whose only matches are folded says so; Enter in the find box goes to the first entry shown.
- Measured: at 1280 by 800 the tab is 5,545 px (16,700 before), the glossary closed 4,569 px; at 400 px the tab is 10,854 px (23,300 before).
- Evidence: kit checker `--quick` 0 problems; clipcheck `--quick` with a new "glossary open" state; `test_report_build.py` pins the new markup; impeccable's detector 0 findings.
