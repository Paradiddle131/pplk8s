## 2026-11-06 — Semantic track — the set-versioning rule and hard-v2's pre-registered criteria (#376)

- Done: `docs/research/semantic-bet/RULE.md` § Set versions, written before any `hard-v2` case is drafted: a set version is a new set name and file naming what it supersedes, never an edit; runs of byte-identical cases are carried with `carried_from` and the SHA-256 of their scoring inputs, refused when the hash differs; the report shows the superseded version until the owner's go.
  It also holds `hard-v2`'s groups (`covered`, `composable`, `uncovered`), its kind `sql_hard`, the ten-kind SQL-difficulty rubric and the four pre-registered criteria, word for word from epic #375's plan, dated 2026-11-06T09:18Z.
  `semantic/PLAN.md` SL-25 has the dated decision; the register has Q12.
- Evidence: `git diff --check` passes; no set was drafted and no arm ran before this commit.
- Open: #377, the blind draft and the freeze.
