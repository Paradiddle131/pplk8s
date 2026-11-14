# Variant C: the browser in place

"See all N" opens no overlay: the guide's right-hand panel becomes the browser in the spot where the example card sat, listing the kind's questions by name with a search, and a picked question opens in the guide's own card in that same spot.
The three lists on the left stay and become the browser's filter, "Every question" widens to all 131 in one step, and "Back to the guide" (or Escape) puts the guide back, on the question last opened when it is of the guide's kind.

## Choices

- **The guide's own card, not a copy.** A question opens in `#qs-card`, filled by the guide's own renderer through one seam line the guide's script would gain (`root.qsBrowse = { show, restore }`, quoted at the top of `section.html`); nothing about the card is forked, and its fixed field heights hold.
- **The left lists are the filter.** While browsing, picking a kind on the left (or a kind chip in an open card) narrows the browser to that kind instead of leaving it; with "Every question" on, the kind on the left is only outlined, since it no longer filters.
- **Rows are an index, not a table.** Each row is the question's readable name (serif, the owner's "orders one day" list) with its first wording beneath in italics; no numbers, no dots, no set-version or "new in" tags. The only numbers shown are labelled ("40 questions", "35 of 131 questions match", "Question 6 of 131").
- **Search** matches names and wording (accents folded) and marks the hits; an empty result offers "Clear the search" and, in a kind, "Search every question".
- **Three levels, one trail.** Guide → list → card; "Back to the guide" sits above, "Back to the list" with Previous and Next through the (filtered) list sits over an open card. The last opened row keeps an ink mark, and the list comes back at the scroll position it was left at.
- Only the page's tokens and type (STIX Two Text, Barlow Semi Condensed); the scope switch and search reuse the glossary's and nav's control styles; one 160 ms fade on view change, off under reduced motion.
- `section.html` also shows only the open kind's "See all N" (`.qs-seeall:not([data-current])` hidden), since the guide renders one button per kind.

## Long lists

The list lives in its own scroll box under the card's top rule, sized to the screen (`min(34rem, 100vh − tab bar − 230px)`, at least 15rem; on a phone at least 16rem), with `overscroll-behavior: contain` and shadows at the top and bottom while more rows wait.
All rows are in the DOM (131 at most today, trivial); past a few hundred questions the row builder would want windowing, which the box already allows.

## Keyboard

Opening focuses the browser's heading; Tab then runs: the kind's tooltip term, the two scope buttons, the search, the list (one tab stop, roving); Shift+Tab reaches "Back to the guide".
In the list: Up and Down, Home and End, Page Up and Page Down; Down from the search enters the list and Up from the first row returns to it; Enter opens a question and focuses its name.
Escape steps back one level: clears a non-empty search first, then card → list (focus on the row opened), then list → guide (focus on "See all N"). A pinned tooltip takes Escape first.

## Checked (Playwright, `check.js`, 70 checks, 0 failures)

At 1280 and 390 px, light and dark: one see-all per kind; open from Uncovered (40 rows) and then Period (18) from the left lists; the list scrolls inside its box (2228 px of rows in a 542 px box at 1280); widen to 131; search narrows (35 for "revenue"); empty state; a question opens in the card; back to the guide restores the stepper and card; no horizontal page scroll; no console errors.
Keyboard only at 1280: Tab reaches See all, the tab order above, arrow keys, Enter opens, Next steps, Escape from card to the row, Escape clears search, Escape closes with focus back on See all, and the guide then shows the question last opened.
Screenshots in `shots/` (deviceScaleFactor 1); `python3 make-preview.py` rebuilds `preview.html` from `report/index.html`, then `node check.js`.

## Not checked

A screen reader (only the roles, labels and live regions are in place), touch scrolling on a real phone, widths between 390 and 1280 other than by the existing breakpoints, `tools/clipcheck.js` on the preview, and the glossary test (no new term appears: the only terms shown are the kind names, which already have entries).
