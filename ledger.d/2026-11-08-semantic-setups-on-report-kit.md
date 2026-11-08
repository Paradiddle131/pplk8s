## 2026-11-08 — Semantic track — the report's Setups tab on report-kit

- Done: the Setups tab on the kit: the setup explorer and the setup map are kit sections with the kit's heads, the panel maps the report's paler inks, rules and bands onto the kit's (`.st`, as `.mfa` and `.er`), and their words follow the one type standard (the kit's family, 1rem, full ink; setup ids in mono at .9375rem).
- Done: no text says how to use either section ("Hover or tap …", "Escape lets go", "The map scrolls sideways", "Arrow keys move …", "Pick a setup …"); captions that say what a mark means stay.
- Done: every focusable part of both sections wears the kit's focus ring; the map's parts had none the kit checker could see.
- Fixed on the way: the kit's dark-ground tracking pushed a measured sequence label in the explorer 3 px past its sheet (clipcheck); the sheets' text keeps no tracking. Issue numbers in the question sets part's style and script comments, which reached the page's source and which the kit checker read as four raw colours.
- Evidence: the kit checker `--quick`: `#setups` 24 findings → 0, 29 → 1 in all (the one left is Question sets', at 200% text); `test_report_build.py` with a new test for the tab.
- Done (owner, 2026-11-08): both sheets redrawn at the chart size, every label 14px (ids 13px in mono) at one unit a pixel, where they rendered at 8 to 13px: the map lays itself out from its width (944 to 1200 px) with measured, wrapped labels and no longer shrinks to the screen's height; the explorer and its sequence draw at their own widths, and each sheet takes its setup's own height.
- Open: Question sets and Method & glossary.
