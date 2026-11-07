# Revision 2: the owner's review of revision 1 (2026-11-04T22:40Z)

Work in place on `docs/research/semantic-bet/report/` (`template.html`, `build.py`); rebuild with `python3 build.py ../results.json`.
Don't touch git; the orchestrating session commits.
Same rules as before: every number from the data, the artifact page contract, both themes, 400 px, no overlapping text, the content rules (no cost, no issue numbers or file names, no notes about the owner's conditions).

## Tooltips: hover as now, click to pin

- Hover keeps working as it does.
- A click on anything that has a tooltip pins it: the tooltip stays where it is and its text can be selected, double-clicked and copied (`pointer-events: auto`, `user-select: text` while pinned), with a small close mark.
- While one tooltip is pinned, hovering anything else shows no other tooltip.
- A click on another tooltip-bearing element moves the pin to it; a click anywhere else (or Escape) unpins.
- Keyboard: Enter or Space on a focused element pins; Escape unpins and returns focus.
- Touch: a tap pins (there is no hover); a tap elsewhere unpins.

## Term tooltips

- Every term the glossary defines gets the same short tooltip wherever it appears in a heading, column header, legend or pillar: covered, hidden-rule, uncovered, conversation, confident-wrong, over the floor, the floor, managed best, decides, check, pending, partial pass, 95% interval, frozen set, hard set (one short sentence each, from the glossary's own text; one source).
- Mark them as the setup names are marked (the dotted underline), so the reader learns one convention.

## Theme switch

- A small switch at the top right: sun and moon icons (inline SVG, drawn, no emoji), an accessible label, `aria-pressed`.
- It sets `data-theme="light"` or `"dark"` on the root; the first visit follows the system; the choice is kept in `localStorage` (wrapped in try/catch).
- Canvases and SVGs re-render on a theme change, so nothing keeps the old theme's colours.
- Check every view in both themes for contrast (text at least 4.5:1 on its ground, marks at least 3:1); fix anything that loses readability.

## Figure 2: a threshold glider on each panel

- Each panel (right, confident-wrong) gets a draggable threshold: a vertical line with a handle on the axis, moving in steps of one percentage point (pointer drag, arrow keys when focused, Shift+arrow for five).
  - Right panel: rows whose mean is below the threshold are dimmed.
  - Confident-wrong panel: rows whose mean is above the threshold are dimmed.
  - The handle shows its value while dragged; a short live line under the figure says how many setups pass ("14 of 31 setups at or above 92% right").
- Its home is the managed best's value, drawn where the managed-best line is now.
  - Returning home without a reset button: the handle snaps to the managed-best line when dragged within two points of it (a small magnetic detent, with the line brightening as it catches), and double-clicking the handle or pressing Home returns it there.
  - When it sits home, the panel reads exactly as it does today (no dimming).
- It must feel solid: no jitter, no lag on a phone, a hit area of at least 24 px, the value never off the axis, and dimming that animates under 150 ms (none under `prefers-reduced-motion`).

## Other changes

- Remove the "Show every model" button. Each setup's other models start collapsed; its own "+N models" toggle expands it.
- The unit plate (Figure 6) opens on the hard set.
- Pending setups: tagged only, never greyed (the owner's last word).
- "Frozen set" and "hard set" in the winners band and elsewhere get the term tooltip (above).
- Prose that carries numbers (the abstract, the figure titles, the pillars' sentences): keep the words, make them easy to scan.
  - Research briefly how good statistical reports and dashboards make number-heavy text readable (for example parallel structure, a small table or two-column layout for the two sets, numbers aligned with tabular figures, interval set smaller and lighter than its mean, the takeaway first in bold or as a lead line), pick what fits, and apply it.
  - The abstract in particular: the frozen set's sentence and the hard set's sentence must be visually separate and parallel, so the eye can move from a number on one set to its twin on the other (for example a two-column abstract with the same row order, or one lead sentence plus a compact two-row comparison).
  - Name in NOTES.md what you chose and why.

## The two setup sections (built by two other agents in parallel)

Two other designers each build one section explaining the setups; both go at the bottom, before "Method, briefly", so the owner can compare and keep one.
Add this contract to the template and build, exactly:

- `build.py` inserts, at a `<!--SECTIONS-->` placeholder after Figure 6 and before "Method, briefly", every `report/sections/<name>/section.html` in name order (a fragment: one `<section>` with its own scoped `<style>` and `<script>`); a missing directory inserts nothing.
- The page exposes, before any section script needs them:
  - `window.REPORT`: the embedded data object (read-only use).
  - `window.reportReady(fn)`: runs `fn` once the page's own rendering is done (immediately if it already is).
  - Delegated behaviour any section gets for free by markup alone: `data-setup="<arm>"` shows that setup's tooltip, `data-term="<term>"` shows a term's, both with the pinning rules above; and any element with class `focusable` that contains `.mk` elements carrying `data-arm` / `data-key` / `data-fam` gets hover-to-focus (wire this by delegation, so elements added later work too).
  - `window.reportTheme()`: returns `"light"` or `"dark"`, and the page dispatches a `report-theme` event on `document` when it changes.
- Sections style themselves only through the page's tokens (`--paper`, `--paper-2`, `--ink`, `--ink-2`, `--ink-3`, `--rule`, `--grid`, `--grid-major`, `--da`, `--gt`, `--mf`, `--ref`, `--other`, `--cw`, `--serif`, `--label`, `--code`); keep those names stable.
- Write the contract in two lines at the top of `build.py`'s docstring.

## Verify

Same as revision 1 (Playwright at 1280 and 400 px, light and dark, no console errors, no horizontal page scroll, the text-overlap script reporting none), plus:
- pin a tooltip, select its text programmatically, confirm hovering elsewhere shows nothing, click another element and confirm the pin moved, click empty page and confirm it closed;
- drag each glider (pointer events) and step it by keyboard; confirm the dimming counts and the snap home;
- the theme switch flips every view, and a contrast check passes in both themes;
- a stub `sections/zz-check/section.html` using `data-setup`, `data-term`, `.focusable` and `reportReady` works; delete the stub after.
Update NOTES.md; deliver `index.html`, `desktop.png`, `phone.png`, `pinned.png`, `glider.png`, `dark.png`. Time box about 60 minutes.
