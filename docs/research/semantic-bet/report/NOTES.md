# Report notes: revision 2

Direction kept: a research memo in a scientific-paper register (STIX Two Text, Barlow Semi Condensed labels, graph-paper plots, blue-black ink), with B's scatter and strip plot and C's unit plate.
Build: `python3 build.py ../results.json`.

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
  Figure 2 (one Plot per panel, side by side, stacked under 700 px), Figure 3, Figure 4, Figure 5 (one Plot per family) and the unit plate of Figure 6 (one Plot of rects per row, replacing the canvases, plus the small interval charts beside each row).
  Plot draws the frames, grids, axes, rules, interval links, lines and the role glyphs (custom Plot symbols that draw the page's own circle, square, diamond and triangle for a radius r); the y layouts that stack families, sets and lanes stay the page's own, passed to Plot as identity scales.
- What stayed outside Plot, and why:
  - The winners band, the decision map, the abstract and twin tables, the legends and the glossary stay HTML.
  - The page's own tooltip, pinning, hover-to-focus, row band and glider: Plot's `tip` mark cannot pin, select or move a pin, so a render transform (`tag()`) reads each element's datum from Plot's binding and adds the `data-tip` / `data-setup` / `data-term` attributes and the `.mk[data-key|data-arm|data-fam]` wrapper the delegated handlers need; the sections contract is unchanged.
  - The glider is a function mark: hand-drawn SVG placed with Plot's x scale, with its old pointer and keyboard handlers.
  - Label placement that avoids collisions (Figure 3's two labels, Figure 5's right-hand labels) is still computed by the page, then drawn as Plot text.
- Behaviour changes, all deliberate:
  - Colours reach Plot as `var(--token)` strings, so a theme switch restyles every figure with no redraw; the `report-theme` event still fires and only closes a pinned tooltip.
  - The row band of Figure 2 now lights up in both panels at once (a delegated handler marks every hit area of the hovered or focused row).
  - Each Figure 2 row and set is one keyboard stop (the band in the right panel), where the stacked phone layout had two.
  - The plate's column labels move right when one would run into the previous label on its tier (the hard set at 400 px overlapped by about 1 px before).
- Vendored: `@observablehq/plot` 0.6.17 and `d3` 7.9.0, the UMD builds from the npm tarballs (integrity checked against the registry), listed with their sha256 in `vendor/README.md`; `build.py` inlines them and refuses to build if a file's sha256 differs. The page grew from 359 kB to 858 kB.
- Measured in Chromium at 1280 px (median of five loads, render plus two frames):
  - The plate on the hard set (its opening view): 82 ms with Plot, 27 ms with canvas; on the frozen set, 150 ms against 30 ms. Both stay under the 200 ms budget, so the plate moved to Plot.
  - A theme switch: 49 ms, down from 87 ms, since nothing redraws.
  - The page's own load (DOMContentLoaded after the response): 594 ms, up from 423 ms, mostly parsing the two libraries.
- Checks:
  - Every number the old page shows is on the new one: the visible numbers of both pages, per figure and with each set selected, match one to one (2,080 at 1280 px, 2,056 at 400 px).
  - 1280 and 400 px, light and dark, each set: no console errors, no horizontal page scroll, no overlapping text among 1,497 to 1,623 text boxes.
  - Hover, click-to-pin, select, hold, move and close, Escape, slopes focus, the glider (+1 to 2% with 43 rows dimmed, Shift+5 to 7% with 13, Home), a 40 px drag (83%, 41 rows) and double-click home, the plate's hover and pin, both setup sections' own focus and tooltips, and the theme switch give the same results as the old page.
  - Contrast, computed from the rendered figures: text at least 5.56:1 (light) and 6.49:1 (dark); data marks at least 3.26:1 and 3.25:1. Under `prefers-reduced-motion` the transitions are 0 s and Plot adds no animation.
