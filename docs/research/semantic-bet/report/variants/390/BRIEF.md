# Brief: a section that explains the question sets (#390)

The report (`docs/research/semantic-bet/report/`, built by `build.py` from `template.html` and `../results.json`) compares about twenty setups that answer a shop owner's business questions over a warehouse.
It measures them on question sets: `frozen` (the first, 96 questions written, 76 scored), `hard` (v1, 43 written, 41 scored) and `hard-v2` (v2: v1's 43 unchanged plus 15 new questions hard in SQL; 58 written, 55 scored; not yet shown in the report's figures, only in its appendix).
Today the page names sets, groups (`covered`, `composable`, `uncovered`, `trap` shown as "hidden-rule", `conversation`), kinds (`sql_hard`, `jargon`, `period`, ...) and retirements, but a reader cannot see what a set holds, and a question's text is reachable only by hovering one square of the unit plate.
The owner wants one section that explains the sets and lets a reader browse every question only if they want to.
Three designers draft it in parallel with different approaches; the owner keeps one. You are one of them; your approach is at the end of your prompt.

## What to show

Per set: what it tests (in plain words), how many questions it has as written and as scored, how many are retired and why (the register's classes: a wrong expected SQL, a fixture that fixes the answer, more than one reasonable reading), its group mix, when it was frozen and its file hash (short, with the full one on demand), whether the report shows it or keeps it in the appendix, and for `hard-v2` what it supersedes and why.
Per question, on demand: its text (every turn of a conversation), its groups and kinds (and for v2's new ones their SQL-rubric kinds: fan-out join, ratio of sums, window, median, anti-join, date spine, fiscal or timezone boundary, ...), the expected answer (the numbers each turn must carry), whether it is new in v2, whether it is retired and the reason, and, for a set the report shows, every setup's outcome on it (right, declined, wrong, confident-wrong, unclear, per run).
Why a question is hard: its kinds, and for a trap or a v2 question the fact that its obvious SQL gives another number (`naive: true` in the data).

## The data (read-only; never invent a fact)

- `window.REPORT.questionSets[<set>]`: `label`, `shown` (in the figures), `appendix`, `frozen` (date), `sha256`, `supersedes`, `supersedes_why`, `groups` (scored cases' groups), `new`, `retired` (ids), and `questions[]`: `id`, `turns[]`, `groups[]`, `kinds[]`, `rubric[]`, `naive`, `new`, `expected` (per turn, a list of accepted numbers or alternatives; a rate is a fraction, 0.35 means 35%), `retired` (null, or `{class, reason, date}`).
- `window.REPORT.sets[<set>]` for the shown sets: `cases[]` (ids in the unit plate's order) and `rows[]` (one per setup and model: `arm`, `modelLabel`, `family`, `role`, and `units`, a string of three characters per case in `cases` order: `0` right, `1` declined, `2` wrong, `3` unclear, `4` confident-wrong, `.` not run). Read `template.html`'s unit plate code for the exact decoding and colours, and reuse its conventions.
- `window.REPORT.buckets`, `window.REPORT.terms` (the glossary: reuse its keys with `data-term`), `window.REPORT.ladder`, `window.REPORT.familyLabel`.
- For meaning, read (never edit): `docs/research/semantic-bet/RULE.md` (§ The set, § Set versions, § Retiring a defective case), the header comments of `services/semantic-agent/evals/semantic_bet.yaml`, `semantic_bet_hard.yaml` and `semantic_bet_hard_v2.yaml`, and `docs/research/semantic-bet/findings/2026-11-06-377-hard-set-v2.md`.

## The contract with the report (fixed)

- Deliver `docs/research/semantic-bet/report/variants/390/<your-dir>/section.html`: a fragment holding one `<section>` with its own `<style>` (every selector scoped under your section's class) and `<script>` (one IIFE starting `window.reportReady(() => { ... })`). It is inserted near the bottom, before "Method, briefly". No other file of the repository is yours to edit; don't touch git.
- Give each set's block an element `id="qs-<set>"` (for example `qs-hard-v2`), so set names elsewhere can later link to it.
- Markup you get for free: `data-term="<key>"` (a glossary term's tooltip, pinnable), `data-setup="<arm>"` (a setup's tooltip), `data-tip="<row id>"` (a row's tooltip).
- Style only through the page's tokens (`--paper`, `--paper-2`, `--row-band`, `--ink`, `--ink-2`, `--ink-3`, `--rule`, `--grid`, `--grid-major`, `--da`, `--gt`, `--mf`, `--ref`, `--cw`, the outcome colours `--o-right`, `--o-decl`, `--o-wrong`, `--o-cw`, `--o-none`, and fonts `--serif`, `--label`, `--code`); inline SVG or HTML; no external script, font or image.
- Keep the page's length in check: the section is compact when closed; long lists are collapsed by default.
- Works at 390 px wide (16 px gutter, no horizontal page scroll; a wide table may scroll inside its own box), in light and dark, keyboard-reachable, `prefers-reduced-motion` respected, text contrast at least 4.5:1.
- Content rules: plain English for a newcomer and exact for a data lover; no cost, no issue numbers, no file names, no notes about the owner; numbers only from the data.
- Design: read `REVISION-2.md` and `template.html` for the page's look, and use the `frontend-design` skill (if it is not in your skill list, read `/mnt/skills/public/frontend-design/SKILL.md`) against generic looks; the section must feel native to this page, not a widget pasted in.

## Preview and evidence

- Build a preview with your section inserted: `cd docs/research/semantic-bet/report && python3 build.py ../results.json --section variants/390/<your-dir>/section.html --out variants/390/<your-dir>/preview.html`.
- Check it in Chromium with Playwright (`require('playwright')` works; don't install it): no console errors, every interaction works (search, filters, expanding, keyboard), at 1280 × 900 and 390 × 844, light and dark (the page's theme switch sets `data-theme` on `<html>`; or emulate `colorScheme`).
- Save screenshots at `deviceScaleFactor: 2` in `variants/390/<your-dir>/shots/`: at least desktop light (closed), desktop dark (a question open), phone light (the list searched or filtered), phone dark; crop to your section (`locator.screenshot`).
- End with a short note (`variants/390/<your-dir>/NOTE.md`, under 15 lines): the idea, what a reader does with it, its trade-offs, and anything you could not verify.
