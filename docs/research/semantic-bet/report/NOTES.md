# Report notes: revision 2

Direction kept: a research memo in a scientific-paper register (STIX Two Text, Barlow Semi Condensed labels, graph-paper plots, blue-black ink), with B's scatter and strip plot and C's unit plate.
Build: `python3 build.py ../results.json`.
Set versions (RULE.md § Set versions, #378): the page shows one version of each set family, `hard` (v1) until the owner's go on #380, then `hard-v2` with `--show hard-v2` (or `BET_REPORT_SHOW=hard-v2`, and #381 flips `SHOWN`); the other version goes to the appendix, "Appendix: other versions of a question set", labelled not yet adopted or superseded, with its numbers from `results.json`.

## What changed in revision 2

- Tooltips, click to pin: hover works as before. A click, a tap, or Enter/Space on a focused element pins the tooltip in place. Pinned text can be selected and copied (pointer events on, user-select text) and has a drawn close mark. While a tooltip is pinned, hovering shows nothing else. A click on another tooltip-bearing element moves the pin; a click anywhere else unpins, and so does Escape, which also returns focus to the element.
- Term tooltips: the fifteen glossary terms are one list in `build.py` (`TERMS`). The glossary and every term tooltip read that list. Terms are marked like setup names (dotted underline) in headings, column headers, legends, tags, pillars, set labels and SVG axis labels.
- Theme switch at the top right: drawn sun and moon, `aria-pressed`, `data-theme` on the root, kept in `localStorage`. The first visit follows the system. A change fires `report-theme` and re-renders every view, the plate's canvases included.
- Contrast: a token check found faint marks below 3:1. The wrong-outcome pink (light) and the not-run dot (both themes) were darkened. Every text token now passes 4.5:1 on every ground, and every data mark 3:1, in both themes. Hairline rules and separators are decoration, so they were left out of the check.
- Figure 2's threshold glider: each panel has a draggable threshold with handles at the top and bottom of the axis. The hit area is 28 px wide over the full panel. The value moves in one-point steps, by pointer or by arrow keys (Shift for five), and stays clamped to the axis. Its home is the managed best: dragging within two points snaps it there, and the line thickens as it catches. Double-click or Home also returns it home. At home nothing is dimmed. Away from home, the rows beyond the threshold dim within 120 ms (no animation under reduced motion), and a live line gives the count per set. Updates are batched per animation frame and touch only the gliders and the marks' classes.
- Removed the "Show every model" button; each setup's "+N models" toggle remains. The unit plate opens on the hard set. Pending setups stay tagged and are never greyed.
- Sections contract, at the top of `build.py`'s docstring:
  - Every `sections/<name>/section.html` is inserted at `<!--SECTIONS-->`, before "Method, briefly".
  - An early script defines `window.REPORT`, `window.reportReady(fn)` and `window.reportTheme()` before any section script runs.
  - The tooltip and hover-to-focus handlers (`data-setup`, `data-term`, `.focusable` with `.mk[data-arm|data-key|data-fam]`) are delegated on `document`, so markup added later works.

## Number-heavy prose: what I chose and why

- Takeaway first: the abstract opens with one bold lead sentence. It is a template over the paired intervals and states only the direction, so the eye gets the claim before the numbers.
- Sets as columns, measures as rows: the abstract's numbers sit in a small table with one column per question set and the same row order. A number on the frozen set and its twin on the hard set sit side by side on one line, and the layout fits 400 px with no sideways scroll.
- Means bold, with the interval set smaller and lighter, in tabular figures, right-aligned. This is the convention of good statistical tables: the estimate reads first and the uncertainty stays beside it.
- Two-set figure titles (Figures 1 and 4) are a single lead sentence over a compact twin table of the per-set facts, instead of one long sentence that alternates sets.
- Pillar sentences keep their words, with numbers set bold and tabular.

## How I checked

- Playwright at 1280 and 400 px, light and dark, with each set selected: no console errors and no horizontal page scroll. The overlap script checked 7,578 text boxes in the abstract, winners and all figures, and found no overlaps.
- Pinning: I pinned a tooltip, selected its text programmatically (user-select text, pointer events auto), hovered elsewhere (the pin held), clicked another name (the pin moved), clicked empty page (it closed), pressed Enter on a focused name (it pinned) and Escape (it unpinned, focus returned). Tap to pin and tap elsewhere to unpin also passed on a 400 px touch device; the tooltip stayed between 8 and 348 px of the 400 px width.
- Gliders:
  - Pointer drag 40 px left on the right-panel handle: the value went to 83% and 37 marks dimmed.
  - Dragging back to within two points snapped it home, with no dimming.
  - Keys +1 then Shift +5 on confident-wrong: the value went to 7% and 15 marks dimmed; Home and double-click returned both home.
- Theme switch: it flips `data-theme`, `aria-pressed`, the body ground, `localStorage` and the event.
- A stub `sections/zz-check/section.html` used `data-setup`, `data-term`, `.focusable` and `reportReady`. Its setup tooltip, term tooltip and hover-to-focus all worked, `reportReady` saw `REPORT` and it received `report-theme`. The stub was then deleted.
- Another designer's `sections/a-setup-map/section.html` already exists and was included by this build.

## Open questions

- Should the glider count unique setups rather than setup-and-model rows?

## After revision 2

- The owner, 2026-11-05: "The new revision is good"; the pick between the two setup sections is still theirs.
- The owner, 2026-11-05T19:50Z: "I wanna keep both for now I loved both equally": the setup map and the setup explorer both stay, in that order, before "Method, briefly".
- The explorer's "What changes" list: a piece swapped for another of the same title (the instruction reworded, as from `custom-metricflow` to `custom-hybrid`) no longer reads as the same line added and dropped; such a pair carries its first line, so the two read apart.
  Checked in Chromium: `custom-hybrid` shows "+ Instruction (given): metrics first; …" and "− Instruction (given): use only the metrics; …", with no console errors.

## Observable Plot port

- What moved to Plot: every figure's drawing.
  - Figure 2: one Plot per panel (their x scales differ), joined into one SVG on wide screens as the page had it, stacked under 700 px.
  - Figures 3 and 4: one Plot each. Figure 5: one Plot per family.
  - Figure 6: one Plot per row of squares (in place of the canvases), plus the small interval charts beside each row.
  - Plot draws the frames, grids, axes, rules, interval links, lines and role glyphs (custom Plot symbols that draw the page's own circle, square, diamond and triangle for a radius r); the y layouts that stack families, sets and lanes stay the page's own, passed to Plot as identity scales.
- What stayed outside Plot, and why:
  - The winners band, the decision map, the abstract and twin tables, the legends and the glossary stay HTML.
  - The page's own tooltip, pinning, hover-to-focus, row band and glider: Plot's `tip` mark cannot pin, select or move a pin. A render transform (`tag()`) reads each element's datum from Plot's binding, and the elements are then regrouped (`collector()`): each moves, inside a shallow copy of its mark's group so it keeps that mark's styling, into per-row groups in reading order. The figures keep the hand-drawn page's DOM: `.mk[data-key|data-arm|data-fam]` around each setup, one focusable `[data-tip]` group per row and set holding its hit area and marks, and the old tab and screen-reader order. The sections contract is unchanged.
  - The glider is hand-drawn SVG placed with Plot's x scale, with its old pointer and keyboard handlers.
  - Figure 5's right-hand labels are placed by the page, as before.
  - Figure 3 names its two key setups with rings and a key instead of placed text (below).
  - Figure 6 draws its squares as one path per outcome colour (outlines as one-pixel rings) rather than one element per square, and each small interval chart is a Plot scale and zero rule with one function mark; four Plot marks per chart, or a rect per square, made the set switch three to five times slower.
- Behaviour changes, all deliberate:
  - Colours reach Plot as `var(--token)` strings, so a theme switch restyles every figure with no redraw; the `report-theme` event still fires and only closes a pinned tooltip.
  - Figure 3's two key setups are ringed on the plot, above every other mark: the managed best with a solid 2 px ink ring, the deciding setup with a dashed one. A two-entry key under the plot shows each ring with the setup's name and role ("native-context-bare, Gemini default, thinking — managed best"; "custom-metricflow, Nemotron free — decides"). Hovering or focusing an entry focuses that setup on the plot and shows its tooltip, through the page's own `data-key` and `data-setup` handlers.
    A text label still shows beside a ring, but only where it fits touching its own mark: 5 px from its glyph, covering no glyph, ring or other label, and nearer its own glyph than any other; otherwise the ring and the key carry the name, and there are no leader lines. The label is anchored on the side that touches the mark and placed once the web font has loaded (waiting at most 1.5 s); a font that lands later can only drop a label that no longer fits, never move it.
    On the hand-drawn page the managed-best label covered the MetricFlow mark and took its hover.
    Today the deciding setup keeps a direct label at 1280 px on both sets; the managed best, in the crowded top right, and both setups at 400 px, go by ring and key.
  - The plate's column labels move right when one would run into the previous label on its tier (the hard set at 400 px overlapped by about 1 px before).
  - The zero rule of the plate's small charts is drawn on the pixel grid (Plot's half-pixel offset), so it is a crisp 1 px line where the hand-drawn one spread over two.
- Vendored: `@observablehq/plot` 0.6.17 and `d3` 7.9.0, the UMD builds from the npm tarballs (integrity checked against the registry), listed with their sha256 in `vendor/README.md`; `build.py` inlines them and refuses to build if a file's sha256 differs. The page grew from 359 kB to 866 kB.
- Measured in Chromium at 1280 px, median of seven loads (render plus two frames), hand-drawn page against the Plot page:
  - Figure 6's switch to the frozen set: 26 ms against 48 ms; to the hard set: 29 ms against 35 ms.
  - A theme switch: 95 ms against 48 ms, since nothing redraws.
  - The page's own load (DOMContentLoaded after the response): 425 ms against 571 ms, mostly parsing the two libraries.
- Checks, old page against new:
  - Every number the old page shows is on the new one: the visible numbers per figure, with each set selected, match one to one (2,080 at 1280 px, 2,056 at 400 px).
  - 1280 and 400 px, light and dark, each set: no console errors, no horizontal page scroll, no overlapping text among 1,497 to 1,623 text boxes; Figure 5's label boxes that touch by 2 px are the same pairs on both pages.
  - Every Figure 6 SVG renders at its own size (89 of 89), and its squares match the canvases pixel for pixel in both themes.
  - The tab sequences of Figures 2 to 6 are the same stops in the same order (Figure 6 differs only in a canvas becoming an SVG), and focusing each of the 505 stops shows the same tooltip text. Closing a tooltip pinned by mouse returns focus to the mark's group in every figure.
  - Hovering a mark lights only its own row band (and, in Figure 2, the same row in the other panel), as on the hand-drawn page.
  - Hover, pin, select, hold, move, close, Escape, the gliders (+1 to 2% with 43 rows dimmed, Shift+5 to 7% with 13, Home, a 40 px drag to 83% with 41 rows), the plate's hover and pin, both setup sections' own focus and tooltips, and the theme switch give the old page's results.
  - Contrast, computed from the rendered figures: text at least 5.56:1 (light) and 6.49:1 (dark); data marks at least 3.26:1 and 3.25:1. Under `prefers-reduced-motion` the transitions are 0 s and Plot adds no animation.

## Feedback round 2026-11-05 night

- Figure 2's gliders no longer snap.
  Each moves in whole percent from 0 to its axis' end: by dragging a handle (the grab offset is kept, so a handle taken off-centre does not jump), by pressing in the band of the top handle or of the axis (the glider jumps there and follows the drag), and by keys: arrows ±1, Shift ±5, PageUp and PageDown ±10, Home to the managed best, End to the axis' end.
  Sitting exactly on the managed best is the reset state: filled handles, nothing dimmed.
  In the confident-wrong panel the bold light line in dark mode is the managed best's rule at 1%; the glider now sits at 0, left of it.
  The hit area is 28 px wide between the handles and 18 px at the handles, so a press in the bands a few pixels off a handle jumps rather than grabs.
- The gliders off home make one joint filter.
  A row's set (frozen or hard) is out when it fails any glider off home, and an out set's marks dim in both panels, not only in the panel whose glider excluded it.
  A row's setup and model text, each copy of it (one per panel in the stacked layout under 700 px), dims when every one of the row's sets is out, so in every SVG the text dims exactly when all of that row's marks there dim.
  With one glider moved, its panel dims as before and the same sets dim in the other panel too.
  Family headers never dim; the text uses the marks' opacity and 120 ms fade, none under reduced motion.
  The live line counts the rows passing every active threshold, per set.
- The glider's value sits beside its top handle on a 3 px paper halo (a text stroke).
  It moves to the handle's left near the panel's end, and also when on the right it would cross a managed-best rule, so the halo never hides one.
  It shows while dragging, while focused, and whenever the glider is off home.
  Under 700 px the rows start 4 px lower, so the value clears the first family header.
- The winners band shows the n behind each figure: the leader's questions and runs.
  An interval with no spread (every run right, or none) is not shown as [100, 100] or [0, 0]: the page gives the exact two-sided 95% Clopper-Pearson bound over the questions (lower bound 0.025^(1/n) for n of n, upper bound 1 − 0.025^(1/n) for 0 of n), computed in `build.py`, rounded outward and marked with a glossary term, "Exact bound".
  The same formatter serves the abstract table, the decision map's interval cells and the row tooltips; the paired differences keep their bootstrap.
  A figure resting on fewer than 20 questions adds "few questions: reads only large gaps".
  The pillars share grid rows (subgrid), so each set's figure sits on one line across the band; the note on what a set's uncovered questions are sits below the leader.
  The leader is labelled and set bold, and its partial flag names its scope ("partial: 110 of 288 runs over the whole set"), apart from the pillar's own runs.
  When a different setup leads on each set in every pillar, the band says so once above the pillars; otherwise each such pillar says it.
  The frozen and hard terms say what each set's uncovered questions are.
- The setup map, from 1180 px: the rungs and their setups are one list on the left, scrolling in its own column, and the map, its readout and legend sit on the right; both stay in view.
  The section leaves the page column (up to 1456 px, centred, inside the 16 px gutters; the script sets the viewport width without its scrollbar).
  The readout keeps the height of its longest text (any setup, rung or part, measured off-screen at the column's width), so it never moves; the map takes the rest of the viewport's height, never under 78% of the 1148 px it has in the page column and never over its column's width; the legend comes last and is the first to go below the fold.
  To keep the readout short, its facts run their names in, and one family's models read once ("Claude Code: Haiku; Sonnet; ...").
  Measured in Chromium with overlay scrollbars, in the sticky state (map width against 1148 px; worst last readout line against the viewport's bottom, over every setup and rung):

  | Viewport | Map | Readout |
  | --- | --- | --- |
  | 1280 × 800 | 895 px, 78.0% (the floor) | fits, 11 px to spare |
  | 1280 × 900 | 986 px, 85.9% | fits, 46 px to spare |
  | 1366 × 768 | 895 px, 78.0% (the floor) | 5 of 25 texts end up to 21 px below |
  | 1440 × 900 | 1022 px, 89.0% | fits, 20 px to spare |
  | 1920 × 1080 | 1194 px, 104.0% | fits, 77 px to spare |

  At exactly 1180 px the map is 886 px, 77.2% (75.9% with a 15 px classic scrollbar, as the review measured; 84.6% at 1280 with one).
  Below 1180 px the stacked layout stays: beside the list the map would fall under about 77% of its size, and on a phone it scrolls sideways in any layout, so the readout carries the facts there.
- Checked with Playwright at 1280 and 400 px, light and dark, each set: both gliders reach every value by keyboard (101 and 51 values) and reach 0, 1, 2, 3, home and the end by dragging a handle; the value's box meets no other text, handle or line at any value, and crosses no managed-best rule; every set's marks dim exactly when the joint filter puts it out, and every text copy matches its row's marks in its own SVG; hovering a setup or rung anywhere in the list highlights the map with both in view; no console errors, no horizontal scroll, no overlapping text, and the tab stops of Figures 2 to 6 are the old ones in the old order.

### Review, two rounds (an independent reviewer with its own Playwright scripts, old page d37d3bf against new)

- Round 1, "fix first": at 400 px a row's text in one stacked panel dimmed for the other panel's glider; with both gliders moved, marks (per panel) and texts (joint) followed two rules; the setup map's readout fell below the fold at laptop heights (up to 145 px at 1366 by 768); the winners' figures did not line up across columns, and "a different setup leads" repeated in every pillar.
  Decided: one joint filter everywhere, the readout's height reserved beside the list, the figures on shared grid rows and the repeated line said once.
- Round 2, "ship": 0 violations of the joint filter in every SVG at every keyboard value and six two-glider pairs at 1280 and 400 px; every value reached by keyboard and by real mouse drag on both panels at both widths (the old page missed 92, 93, 95 and 96 on % right and 0, 2 and 3 on confident-wrong); 0 overlapping text boxes; the tab stops of Figures 2 to 6 unchanged (624, 600 and 717); numbers differ from the old page only in the exact bounds and the winners' new lines; no console errors, no horizontal scroll from 360 to 1920 px, classic 15 px scrollbars included; transitions 0 s under reduced motion; new text at least 5.56:1 (light) and 6.49:1 (dark).
- Left as P3: near 97 to 100% right the readout's halo still covers a few pixels of the managed-best rules (it must sit left of the handle there); Home returns to the managed best, not 0 (the reset the owner asked for); at 1366 by 768 the map sits at its 78% floor and 4 of 95 hovered targets end up to 14 px below the fold; at 1440 by 900 the map is 89% where it was full size, to keep the readout in view.
- The live line no longer says "the others are dimmed" when no row is.

### The owner's question: why "Uncovered questions" reads 93% [83, 100] on the frozen set but 100% [100, 100] on the hard set

Measured from the page's data (results.json at d37d3bf, the logs scored as the eval scores them), 2026-11-06.
- Two different setups lead: on the frozen set `native-kc-max` on Gemini, 29 uncovered questions, 87 runs, 81 right and 6 declined; on the hard set `native-context` on Gemini, 19 uncovered questions, 57 runs, all 57 right.
- The frozen leader's 6 declines are the two temperature questions (`amsterdam_temperature`, `bet_istanbul_warmer`), declined on every run by every managed agent: "the available data ... does not contain weather or temperature records"; the managed agents cannot see the weather table, so 27 of 29 (93%) is their ceiling on that set.
- [100, 100] was the question-level bootstrap collapsing when every run is right: resampling questions that are all right can only give 100%, so it is not a 95% interval.
  The page now shows the exact two-sided 95% Clopper-Pearson bound over the questions instead: 19 of 19 gives a lower bound of 82%.
- The sets are hard in different ways.
  The frozen set's uncovered questions are medians, percentiles, times between events and weather: shapes no metric composes and SQL agents sometimes get wrong (`native-context` was confidently wrong on 15 of its 87 frozen uncovered runs, mostly medians and percentiles; 0 of 57 on the hard set).
  The hard set was built hard on business language (jargon, fiscal and relative periods, implicit definitions, ambiguity; `findings/2026-11-03-356-hard-set.md`); its uncovered questions are mostly ratios and differences of two measures (11 of its 12 `multi_metric` cases are uncovered), ordinary SQL for an agent that writes SQL.
- The owner's expectation about MetricFlow holds: the ratio questions are composable from two metric queries, so MetricFlow on the free model answers more of the hard set's uncovered questions than the frozen set's (61% of 57 runs against 38% of 29 runs; the hybrid 84% of 19 against 52% of 29).
  The cost: on the hard set's uncovered questions MetricFlow was confidently wrong on 6 of 57 runs, against 0 of 29 on the frozen set, where it mostly declines.
- The page also said MetricFlow "declines them by design" next to its 61%: that sentence now reads "which no single metric answers", and the setup's description says it is told to answer only through the metrics.
