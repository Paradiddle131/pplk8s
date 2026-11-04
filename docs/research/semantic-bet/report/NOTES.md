# Variant A, revision 1: the research memo, with B's scatter and strip and C's unit plate

Direction kept: a research memo in a scientific-paper register (STIX Two Text, Barlow Semi Condensed labels, graph-paper plots, blue-black ink), now with every cost, issue number, file name, provenance line, owner-condition note and shade legend removed.

## What changed

- New, near the top: the winners band with three pillars (covered questions, uncovered questions, least often confidently wrong), each with both sets. The leader, its number and its interval are computed from the logs. A setup ties the leader when its paired interval (setup minus leader, over the questions both reached) includes zero, and every tied setup is named.
- The deciding-run rule, data-driven: a setup enters the pillars and every headline only through a row on the model that decides for it. For our setups that is the free model; for Google's agents it is Gemini, the only model they run on. `native-mcp`, `custom-toolbox` and `custom-hybrid` (Claude only) keep their numbers, tagged "pending: deciding run". A free-model row in a new results.json promotes them with no code change (tested, see below). `cc-metricflow` and `baseline` never enter.
- Figure 1 (decision map): both sets in every cell (frozen first, hard second). Cost column and shade legend removed; best-in-column boxes kept.
- Figure 2 (forest): two framed panels, each with its own title and axis title. On a phone they stack into two charts. Both sets sit on one row: the frozen set as the upper mark, the hard set as the lower, hollow mark.
- Figure 3 is B's scatter (accuracy against confident-wrong with crosshair intervals), full width. Figure 4 is B's strip plot by question group, both sets as labelled sub-rows. Figure 5 is the covered-to-uncovered slopes, larger (two panels per row, 360 px tall).
- Figure 6 is C's unit plate, once, in ladder order, replacing my old Figure 4 ladder. The decision map stays the first screen, and the plate carries the ladder job: increments now come from C's "over the floor" column, a paired interval per question. Beside it is a confident-wrong column (rate and interval). Rows and columns have rules and alternating bands, the header is sticky (its horizontal scroll is synced on a phone), there is one square per run and a faint dot per unrun run, and hovering a square shows its question and outcome. No answers are embedded; the page is 184 KB.
- The setup tooltip is one delegated component. Every setup name (pillars, map, forest labels, scatter and slope labels, plate labels) shows that setup's "What this setup is" sentence on hover or keyboard focus, and the tooltip is clamped to the viewport.
- Hover-to-focus on Figures 2 to 5: hovering a mark, line, label or family legend entry keeps that setup, model or family at full strength and dims the rest.
- Captions cut to one how-to-read sentence; the figure title carries the takeaway.

## Both sets: which views take them

- Both sets side by side: the winners band, the abstract, Figure 1 (twin chips per cell), Figure 2 (paired marks per row) and Figure 4 (a sub-row per set).
- A per-view switch: Figure 3 (the scatter), Figure 5 (the slopes) and Figure 6 (the plate).
  - The scatter with both sets would be about 50 crosshairs in one field.
  - The slopes would double the lines and their end labels in every panel.
  - The plate's two sets have different questions, so their columns cannot share an x position.

## Builds that survive new data

`python3 build.py results.json [LOG_DIR] [SETS_DIR]`; LOG_DIR and SETS_DIR default to the repo layout.
An unseen setup gets "Not yet described.", a neutral grey and a "Not yet placed on the ladder" group. An unseen `:free` model counts as the deciding lane. Missing groups, step-two pairs, managed best or set files fall back instead of failing.
Stress test: a results.json with an unseen setup on an unseen free model, a setup with no groups, a free-model `native-mcp` row on the hard set, no step-two pairs and no hard managed best. It built, and the page rendered with no console errors and no overlaps; the new free row was promoted.

## How I checked

- Playwright at 1280 and 400 px, light and dark, each with both sets selected in every switch: no horizontal page scroll and no console errors.
- An overlap script collects every visible SVG text and HTML text-node rect in the winners band and all six figures, clipped to their scroll containers, and flags any two that intersect by more than 2 px. Across the 16 renders it checked 6,102 text boxes; the one hit (the phone forest's managed-best label) was fixed, and it now reports 0 overlaps.
- Tooltips: hovered setup names in the map, forest, plate and winners at 400 px; each showed its own sentence inside the viewport (left 8, right 348 of 400). Keyboard focus on a map name shows it too.
- Hover-to-focus: Figures 2 to 5 enter focus on hover and clear on leave; `hover.png` shows the scatter focused on MetricFlow with its row tooltip.

## Questions for the owner and one weakness

- Should the plate default to the hard set, where the ladder's lift is largest?
- Should pending setups also be greyed in the charts, not only tagged?
- Weakness: per-group shares in the map and strip still carry no interval on the page (the pillars do), so small groups can look more decisive than they are.
