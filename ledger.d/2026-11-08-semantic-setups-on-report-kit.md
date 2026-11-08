## 2026-11-08 — Semantic track — the report's Setups tab on report-kit

- Done: the Setups tab on the kit: the setup explorer and the setup map are kit sections with the kit's heads, the panel maps the report's paler inks, rules and bands onto the kit's (`.st`, as `.mfa` and `.er`), and their words follow the one type standard (the kit's family, 1rem, full ink; setup ids in mono at .9375rem).
- Done: no text says how to use either section ("Hover or tap …", "Escape lets go", "The map scrolls sideways", "Arrow keys move …", "Pick a setup …"); captions that say what a mark means stay.
- Done: every focusable part of both sections wears the kit's focus ring; the map's parts had none the kit checker could see.
- Fixed on the way: the kit's dark-ground tracking pushed a measured sequence label in the explorer 3 px past its sheet (clipcheck); the sheets' text keeps no tracking. Issue numbers in the question sets part's style and script comments, which reached the page's source and which the kit checker read as four raw colours.
- Evidence: the kit checker `--quick`: `#setups` 24 findings → 0, 29 → 1 in all (the one left is Question sets', at 200% text); `test_report_build.py` with a new test for the tab.
- Open: the two sheets keep their drawn text sizes (8 to 13px rendered, under the standard's .875rem inside charts) until the owner says whether to redraw them on a larger label grid; then Question sets and Method & glossary.
