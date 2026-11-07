# Design B: a side drawer (#397)

"See all N" slides a drawer in from the right that lists every question of that kind, A to Z, with the guide's own lists still in view and still live beside it: picking another kind in the guide re-scopes the open drawer.
A question opens inside the drawer to the guide's own card, and one press on "Every question" widens the list to all 131; on a phone the same piece is a modal bottom sheet.

## Choices

- Desktop (over 760 px): a non-modal dialog, `clamp(24rem, 100vw − 340px, 40rem)` wide, with no scrim, so the guide's three lists stay visible and clickable at its left (at 1280 px the lists end at 304 px, the drawer starts at 640 px).
  A kind picked in the guide, by click or arrow keys, re-scopes the drawer; a kind chip in the guide's card does too.
- Phone (760 px and under): a bottom sheet at most 90% of the screen's height, modal (`aria-modal`, the page `inert`, a focus trap, a scrim that closes it, the page's scroll locked).
- The head says what is listed: a small-capital kicker naming the kind's list (Groups, Hard to interpret, Hard in SQL), the kind as a glossary term with "13 questions", and its definition.
- Widening is the page's own `.seg` control: "[Jargon 13] [Every question 131]"; the kind side narrows back.
- "Other kinds" folds out the guide's three lists at once, as chips with their counts and term tooltips, so a phone reader (who cannot see the guide) can switch kinds without closing.
- Each row: the question's readable name and its first turn, clamped to two lines; a conversation says "2 turns".
  No expected numbers, no dots, no set or version tags.
- The card is the guide's card, not a fork: its markup is cloned from `#qs-card` and filled by the guide's own renderer, and its fields reserve their tallest content at the drawer's width, as the guide's do, so Previous and Next never move a field.
  A kind chip in the drawer's card lists that kind in the drawer and pins no tooltip.
- The card view has "‹ All Jargon questions" (back to the list, its scroll and the row kept, focus on that row, the row marked), Previous and Next (wrapping, arrow keys on them) and "Question 3 of 13".
- Tokens, type and controls are the page's (`.seg`, `.qs-btn`, the tooltip's kicker style); no new fonts or colours.

## Long lists

- The list scrolls inside the drawer (`overscroll-behavior: contain`); the page behind never moves.
- A sticky count line ("131 questions, A to Z", or "23 of 131 questions match") heads the list; past 24 rows, sticky initial-letter dividers give landmarks while scrolling.
- "Find a question" filters by every word typed, over the name and every turn, marking the matches; an empty result offers to clear the search or to look in every question.
- Keyboard: ArrowDown from the search enters the list; ArrowUp, ArrowDown, Home and End move along it.

## One seam in questions.html

The drawer needs the guide's card renderer, which is private to the guide's closure: `preview.html` adds one line after `function fill` in the guide's script, `root.qsFill = fill;`.
Landing this design means adding that line to `questions.html` (or moving the drawer's script into that closure).
The preview also un-hides the see-all buttons, and the section shows only the current kind's button (`.qs-seeall:not([data-current])` hidden).

## What I checked

Playwright, Chromium, `preview.html#question-sets`, at 1280 × 900 and 390 × 844, light and dark: 106 checks, 0 failures.
- Opened from Jargon (13 rows) by Enter on its "See all 13" and from Uncovered (40 rows); focus lands on the drawer's heading; `aria-modal` false on desktop, true on the phone; the guide's lists sit wholly left of the drawer at 1280.
- Widened to 131 rows in one press; a 2,500 px wheel scroll moved the list, not the page; the count line stays stuck to the top.
- Search "orders": 23 matches; re-scoped through "Other kinds"; picking Jargon in the guide while the drawer showed Uncovered re-scoped it (desktop).
- Opened a card: all six fields filled, focus on the question's name, the card's height the same after Next, no sideways overflow in the card.
- Back focuses the row last opened; Escape closes and returns focus to the "See all" button (or, if the guide moved to another kind meanwhile, that kind's button); with a tooltip pinned in the drawer, Escape unpins it first and the drawer stays.
- Keyboard only: the tab order is the heading's term, Close, the two scope buttons, search, Other kinds, then the rows; on the phone 60 Tabs never left the sheet; on desktop Tab past the drawer's end moves to the guide's open kind.
- Hovering a kind chip shows its glossary tooltip; clicking it re-scopes and pins nothing.
- No console errors, no horizontal page scroll with the drawer open or a card open.
- Screenshots (device scale 1) in `shots/`: per width and theme, the opened kind, the widened list scrolled, the folded-out kinds, a card, and the guide driving the drawer (desktop) or a keyboard-opened card (phone); plus a kind chip's tooltip.

## What I did not check

- The real web fonts (blocked in this sandbox; fallback faces only), Safari and Firefox, real touch devices, screen-reader output.
- Widths between 760 and 1000 px, where the drawer is at its 24rem floor and covers more of the guide.
- Swipe-to-dismiss on the sheet: not built; the grip is decorative, Close, the scrim and Escape close it.
- The first card opened costs about 340 ms (the reservation measures all 131 questions at the drawer's width, as the guide's card does); later opens reuse it until the width changes.

## Found in passing

The guide's card loses its `aria-labelledby` target on its first render: `#qs-card` points at `#qs-name`, but the renderer redraws the title field without that id (`document.getElementById('qs-name')` is null on the built page).
The drawer restores the id on its own card after each fill; the guide's needs the same fix in `questions.html`.
