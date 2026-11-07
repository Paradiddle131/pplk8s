# Variant B: a contents rail

Grouping, eight chapters in today's order, one open at a time: 1 Summary (abstract, who wins), 2 The decision map (Figure 1), 3 Where MetricFlow stands (Figures 2, 3), 4 Covered against uncovered (Figures 4, 5), 5 Every run (Figure 6), 6 The setups (setup map, then one setup at a time), 7 Question sets (the appendix's more question sets), 8 Method and glossary.
How a reader moves: from 900 px a sticky left rail reads like a paper's contents, each chapter numbered with its figures (or parts) beneath in small type; the open chapter carries an ink bar, the part in view an ink tick.
Choosing a chapter opens it at its top; choosing a figure opens its chapter and scrolls to it; each chapter ends with Previous and Next.
Under 900 px the rail folds into a sticky bar ("3 of 8 · Where MetricFlow stands") that opens the same contents as a sheet; Escape, a tap outside or a choice closes it.
The hash names the chapter (#metricflow) or a place in one (#fig3, #term-covered, #map-<setup>, #setup-<setup>, #other-set-versions); every link, reload, Back and Forward opens the right chapter, and Back restores the scroll position.
The glossary and map jumps open the target's chapter as a history entry, flash the target and show "↑ Back", which returns to the chapter, the scroll position and the element.
Keyboard: the rail is one tab stop (roving tabindex; Up, Down, Home, End; Enter opens), and focus lands on the opened chapter or figure.
Closed chapters stay laid out at the column's width but invisible, clipped and inert, so every figure draws at its real width, also after a resize while closed; leaving a chapter drops its pinned tooltip, locked focus and "↑ Back".
#390's question section goes in chapter 7, Question sets, before the appendix: its `section.html` only needs `data-chapter="question-sets"` on its `<section>` (the template moves it there; no build.py change).
Trade-offs: the rail takes about 224 px at 1280, so the main column is 1024 px instead of 1248; the decision map still fits, but the setup map no longer breaks out of the column and draws at about 760 px instead of about 986.
A chapter is one click away from any other, but reading straight through takes a Next per chapter; the appendix's "the figures above" (build.py text) now points into other chapters.
No new glossary term is needed.
Checked in Chromium (Playwright), 80 checks, all passing, no console errors: every chapter by click, keyboard and URL; Back, Forward and reload; both jumps and "↑ Back" across chapters; resized while closed, Figures 2 to 6 match a fresh load; set switch, glider, hover, pin and theme inside a chapter; no sideways page scroll at 1280 and 390 in either theme; the sticky map head sits under the bar on a phone; reduced motion; new text at least 5.56:1 (light) and 6.49:1 (dark).
Clipped text: `tools/clipcheck.js --quick` as written times out on its first set switch, since that control sits in a closed chapter; a copy that opens each chapter first (checks unchanged) found 0 findings at 1280, 1024, 768, 400 and 360 px in light, dark and the dark button.
Not verified: Safari, Firefox, real touch devices, screen-reader speech, classic desktop scrollbars, and the setup map's layout between 1180 and 1279 px beyond the clip check.
