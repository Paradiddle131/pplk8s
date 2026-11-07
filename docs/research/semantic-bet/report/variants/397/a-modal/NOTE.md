# Variant A: a centred modal

"See all N" opens a native modal `<dialog>` over the report: the kind's questions on the left as a scrolling, searchable list, the guide's own card for the chosen question on the right.
One switch widens the list from this kind to every question, and "Another kind" swaps the list for the guide's three lists at once, so the reader can move between kinds without leaving the dialog.

## Choices

- Native `<dialog>` with `showModal()`: the page behind is inert, the browser gives the top layer and Escape; the dialog adds a Tab wrap so focus never leaves it, closes on the backdrop and the close button, and returns focus to the "See all" button.
- It opens on the question the guide was showing when that question is of the kind, so the reader keeps their place.
- The head names what is listed: the kind as a term (its tooltip and glossary entry) with its definition, or "Every question" with the three sets named as terms.
- The scope switch is two labelled halves: "This kind, 84 questions" and "Every kind, 131 questions"; once widened the first reads "Only covered", so narrowing back is one click too.
- "Another kind" shows the guide's three lists (Groups, Hard to interpret, Hard in SQL) at once as chips, each with its count under the caption "Each kind with its number of questions"; a chip in the card ("Groups", "What makes it hard") also re-scopes the list to that kind and keeps the question.
- Rows show only the question's readable name and how it is first asked (two lines at most), plus "then N follow-up questions" for a conversation; no expected numbers, dots or version tags.
- The card is the guide's `#qs-card`, cloned, and filled by the guide's own renderers; it keeps the guide's fixed layout (each field reserves the height its tallest content takes, measured at the dialog's width).
- Escape is layered: a pinned tooltip closes first, then the kinds panel, then the dialog.
- The page's single tooltip moves into the dialog while it is open (the rest of the page is inert under a modal), into a host placed at the page's origin, so hover and pinned tooltips land under their term; it goes home on close.
  A pinned tooltip's "More in the glossary" closes the dialog and jumps as before.
- Phone (640 px and under): a full-screen sheet in two steps, the list and then the card, with "The list" to go back; Escape still closes.
- Tokens and type only from the page: the backdrop is the paper colour at 62% with a light blur, the frame the ink rule the set profiles use.

## Long lists

- The list scrolls inside its own pane (`overscroll-behavior: contain`); the page never grows.
- A find box filters by name and wording, highlights the match and says "2 of 131 questions match"; an empty result offers "Look in every kind".
- Keys: Up and Down, Home and End, Page Up and Page Down move the selection, which follows focus and keeps itself in view; Previous and Next under the card step through the same filtered list and say "Question 3 of 18".
- 131 rows at most, so no virtualisation; a 1,000-row set would want it.

## Dropping it in

- `section.html` is a style block and a script, like `questions.html`; the script builds the dialog itself and listens for `qs:see-all`.
- It needs one line in the guide's script after `fill`: `window.__qsCard = { fill: fill };` (`preview.html` adds it), and `build.py` to drop `hidden` from the "See all" buttons; `.qs .qs-seeall:not([data-current])` keeps one visible, the current kind's.
- The fixed-height measure is a copy of the guide's `reserve()` pointed at another card; on merge both could share one function.
- Gap found in passing: the guide's `#qs-name` id is lost on the first render (the title renderer writes an `h5` without it), so this script reads `#qs-card .qs-name`.

## Checked (Playwright, Chromium, 1280 x 800 and 390 x 844, light and dark)

- Opened by keyboard from "Covered" (84) and by mouse from "Period" (18); the dialog opened on the guide's current example.
- Widened to all 131, filtered by text, opened "Another kind" and picked "Hidden-rule" by keyboard (15).
- Arrow and Page Down moved the selection to question 14 (desktop) and 16 (phone), the list scrolled to keep it in view; Enter opened the card step on the phone and "The list" returned.
- 60 Tabs and 10 Shift+Tabs never left the dialog; Escape closed the kinds panel first, then the dialog, and focus went back to the "See all" button.
- A term in the card pinned its tooltip right under it inside the dialog (with the page scrolled); Escape unpinned it and left the dialog open; the tooltip went back to the page on close.
- A chip in the card re-scoped the list; the backdrop click (desktop) and the close button (phone) closed it.
- No console errors, no horizontal page scroll, one "See all" visible in the guide.
- Screenshots in `shots/`.

## Not checked

- Real touch devices, Safari and Firefox (`<dialog>`, `:has`, `color-mix` and `line-clamp` are all current there, but untested), a screen reader, and the page's `tools/clipcheck.js` (it does not open the dialog).
- The fixed card leaves tall empty fields at phone width, as the guide's card does; whether the dialog should keep that rule is the owner's call.
