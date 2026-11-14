# Brief: three ways to switch between the report's sections (#396)

The report (`docs/research/semantic-bet/report/`, built by `build.py` from `template.html` and `../results.json`) is one long page today.
The owner wants its sections grouped into tabs, or another way of switching between them, before any further section is built.
Three designers draft it in parallel with different approaches; the owner keeps one.
You are one of them; your approach is at the end of your prompt.

## The owner's words

- On #396, 2026-11-06: "now that we have completely different sections, some of which might go together, like the setups can have both views. We can mostly put these under new tabs, can't we? For instance, the method briefly and glossary can go to one tab, which would be ordered in the last. And we would roughly keep the current order of sections, but not necessarily in one single very long HTML report, but maybe we can have tabs or at least one way of switching between the sections."
- And: "I would like to see the 3 alternatives for switching between tabs functionality before" the question section's detail views are designed.
- On #393, 2026-11-06: "the reader will not care about the things like 'Frozen 6 Nov 2026 · file hash 23b62532'. Make sure the agents are not adding such stuff to the report. Keep only the useful stuff that the user, the viewer of the report would care and would understand at a glance, with limited support like explanations, tooltips, etc. The agents should always know that the reader will not see the code base, our issues, pull requests, our designs, etc. They are just looking at a report."
- On the filters "Any / Scored / Retired / New in a version": "These sections are just cluttering the page."
- On retired questions, 2026-11-06: "remove cleanly. no clutter".

## The reader rule (binding)

The reader sees only the report: never our code base, issues, pull requests, designs, logs or files.
No hash, freeze date, set-version lineage ("v1", "v2", "supersedes"), retired question in any form, pass or run bookkeeping, issue or PR number, file name or the owner's decisions on the page, in a tab name, a tooltip or a URL.
Every term you add has a glossary entry (`build.py` `TERMS`; ask in your NOTE if you need one, do not edit `build.py`).

## The page today, in order

1. Title, byline, theme switch.
2. Abstract: a lead sentence and a small table.
3. "Who wins each kind of question": the winners band.
4. Figure 1, the decision map (a wide table with a sticky head copy, `#maphead`).
5. "Where the ADK agent on MetricFlow stands": Figures 2 (two panels with threshold gliders) and 3 (a scatter with a set switch).
6. "Why: covered questions against uncovered ones": Figures 4 and 5.
7. "Every run, from the cheapest setup to the most custom": Figure 6, the unit plate.
8. The two setup sections, inserted at `<!--SECTIONS-->`: "What each setup is" (the setup map, `sections/a-setup-map/`) and "What each setup is, one at a time" (the setup explorer, `sections/b-setup-explorer/`, which writes `#setup-<arm>` into the URL); the owner keeps both, and they go together.
9. "Appendix: more question sets" (`#other-set-versions`).
10. "Method, briefly" and "Glossary" (each term at `#term-<key>`): together, last.

A section that explains the question sets and lets a reader browse them is coming next (#390: per set, what it tests and its groups, with every question one click away); leave it a place in your grouping, near the figures or beside Method, and say where in your NOTE.

## What your variant must do

- Group today's sections into tabs or views in roughly today's order, the two setup sections together, Method and Glossary together and last.
- Deep links: every tab or view has its own URL (a hash), a reload or a shared link opens it, Back and Forward in the browser move between views; the existing in-page targets still resolve and open the view that holds them (`#term-<key>`, `#map-<arm>`, `#setup-<arm>`, `#other-set-versions`).
- The pinned tooltip's jump keeps working across views: "More in the glossary ↓" and "See its row in the map ↓" (template.html, `jumpTarget` and `jump`) must open the view that holds the target, scroll to it and flash it, and the "↑ Back" button must return to the view and scroll position the reader came from.
- Every figure must draw at its real width when its view is first shown and after a resize while hidden (the figures measure `clientWidth`, which is 0 inside `display: none`); the set switches, the gliders, the focus and dimming rules (one dimming source per figure: hover, a clicked lock, or the glider), the theme switch and every tooltip still work in every view.
- Keyboard: the switcher is reachable and usable by keyboard (for tabs, the WAI-ARIA tabs pattern: arrow keys, Home, End, roving tabindex, `aria-selected`, `aria-controls`); focus lands sensibly when a view opens.
- 1280 × 900 and 390 × 844, light and dark: no horizontal page scroll at 390 px (16 px gutter); the switcher stays usable at 390 px.
- `prefers-reduced-motion` respected; text contrast at least 4.5:1, marks 3:1; style only through the page's tokens (`--paper`, `--paper-2`, `--ink`, `--ink-2`, `--ink-3`, `--rule`, `--band`, `--sel`, the family and outcome colours, `--serif`, `--label`, `--code`).
- Feel native to this page (a research memo in a scientific-paper register: STIX Two Text, Barlow Semi Condensed labels, graph-paper plots); read `NOTES.md` and `REVISION-2.md` first, and use the `frontend-design` skill (if it is not in your skill list, read `/mnt/skills/public/frontend-design/SKILL.md`) against generic looks; no external script, font or image.

## Where you work

- Copy `template.html` to `variants/396/<your-dir>/template.html` and change only that copy (and, if you must, copies of the two sections under your directory, passed with `--section`; say so in the NOTE). No other file of the repository is yours to edit; don't touch git.
- Build the preview: `cd docs/research/semantic-bet/report && python3 build.py ../results.json --template variants/396/<your-dir>/template.html --out variants/396/<your-dir>/preview.html`.
- Check it in Chromium with Playwright (`require('playwright')` works; don't install it): no console errors; every view opens by click, keyboard and URL; Back and Forward; both jumps and "↑ Back" across views; a figure in a view opened after a resize draws at full width.
- Run the page's clipped-text check on your preview: `node tools/clipcheck.js --quick --url file://$PWD/variants/396/<your-dir>/preview.html` (it opens the page at rest, so also open each view yourself and look); report what it finds.
- Screenshots at `deviceScaleFactor: 2` in `variants/396/<your-dir>/shots/`: desktop light on the first view, desktop dark on a figures view, desktop light with a glossary jump done (the target flashed, "↑ Back" shown), phone light with the switcher, phone dark on the setups view.
- End with `variants/396/<your-dir>/NOTE.md`, under 20 lines: the grouping (each view's name and what it holds), how a reader moves, the trade-offs, where #390's question section goes, and anything you could not verify.
