# Brief: the question browser behind "See all N" (#397)

Three designers draft this in parallel, one variant each, for the owner to pick.

## What exists

- The report page is built by `report/build.py` from `report/template.html` into `report/index.html`; the question section (#390, "the field guide") is in the "Question sets" tab, its style and script in `report/questions.html`, its data in `REPORT.questionGuide` (every scored question: id, readable name, sets, turns with expected numbers, groups, kinds, what makes it hard, obvious-SQL trap, each setup's runs).
- Each kind in the guide has a hidden "See all N" button (`hidden`, a comment naming #397); a click dispatches `CustomEvent('qs:see-all', {detail: {category}})` on `document`.
- The guide's fixed card: name and sets, Asked (turns with labelled expected numbers), Groups, What makes it hard, Obvious SQL, How each setup did (a table of setups with their runs, and a plain summary).

## The owner's words (2026-11-06)

- "I still need one sort of view to list all the questions. But not in a different section ... when the user clicks on the 'see all N in the list', Shall we open up a modal, for instance, or some sort of pop-up or whichever would be modern and useful in this case, so that we show the user what they want to see, which is seeing all the questions in a given category, or even maybe with an option to see literally everything if they want to expand the initial filter that they had without having a new section in the report itself."
- On the earlier full lists: "I would hate it to have everything listed fully with no scrolling, pagination, or whatever that would handle the long list"; "I see numbers at the right-hand side, probably the expected value, which is both not really required in this very view ... It doesn't even have a label"; "'new in Hard v2' sounds also quite useless".
- Liked: "seeing the list of metrics, like the orders one day, canceled total, etc. It sort of felt nice to see them listed"; the per-question dots "not really strictly necessary"; group and kind drop-downs disliked ("grouping by them is truly useful", but shown at once, as in the guide's three lists).

## Must

- Opened by "See all N" with that category's filter set; widening to every question in one step.
- Long lists handled: scrolling inside the view, paging or virtualisation; never the whole list poured onto the page.
- No unlabelled numbers; no version, retirement or "new in" tags.
- Each question opens to the same fixed card layout as the guide's card (reuse it, don't fork it).
- The reader rule (`report/NOTES.md`): only what the reader understands at a glance; no process metadata (hashes, dates of freezing, issue numbers, file names); every term shown has a tooltip and a glossary entry.
- Works at 1280 and 390 px, light and dark, keyboard (focus trap if modal, Escape closes, focus returns to the button), no horizontal page scroll.
- The page's own tokens and type; no new fonts or colours.
