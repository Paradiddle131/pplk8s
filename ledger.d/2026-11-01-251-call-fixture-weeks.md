## 2026-11-01 — Semantic — Spread the call fixture over six weeks, so the label-share band and CallLabelShareDrift show end to end (#251)

- Done: `dbt/dev/fixture.sql` adds five weeks of calls before 2026-09-28's (eight a week, reusing recorded texts, so no new label call); `make semantic-check` drops its hand-seeded label shares and asserts the built table: 78 rows over 6 weeks, 52 banded, the newest week's delivery share (0.3333, band 0 to 0.1819) the only one outside its band, and the exporter's 13 series for that week; the emulator check counts 52 labelled calls; the call eval questions keep to 1 and 2 October; runbook § 14.
- Evidence: see the PR for the gate counts.
- Decisions: none.
