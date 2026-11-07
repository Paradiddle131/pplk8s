# C: the field guide

The idea: explain the sets through examples, not tables.
Three set profiles side by side (on a phone, one at a time behind a set switch): what each tests, written / scored / retired with the register's classes, the scored group mix as bars, the freeze date, the short hash (the full one on a click), shown or appendix, and v2's "supersedes" with its reason.
Then a guide with one entry per group, per hard kind and per SQL-rubric kind present in the data: a one-sentence definition, where it occurs, and one real non-retired question as a specimen card (every turn with its expected numbers, groups and kinds as chips, whether the obvious SQL misses, and an outcome strip in the unit plate's squares, one column per setup and model, read by hover or arrow keys); Previous and Next step through the other examples of the same kind.
Examples are ordered by rule, not by id: questions with runs in the figures first, then the plainest member of a group, then the one that splits the setups most, then the most confident-wrong runs, then the sets' own order.
Last, a collapsed "Every question" list (154 distinct ids; hard and v2 share 43) with search, set and status filters, a tag filter fed by the guide's chips and the profiles' retired links, and expandable rows using the same card.
A reader can stay at the profiles, learn the kinds from real cases, or search the full list; nothing long is open by default.
Trade-offs: one specimen at a time hides the spread of a kind (the list's tag filter shows it); the guide's index is long on desktop (21 entries); v2's new questions have no outcome strip until the report shows v2, and the card says so.
Words in the definitions are written once in the section; every number comes from the data. Retirement reasons from the register have tracker numbers and file names stripped at render.
Verified with Playwright in Chromium at 1280 x 900 and 390 x 844, light and dark (system scheme and the page's theme switch): every control clicked, index and strip by keyboard, no horizontal page scroll, the report's clip checker clean at rest, text contrast of the tokens used at least 5.2:1.
Not verified: the Google fonts were blocked in the sandbox, so screenshots use the fallback faces (the only console error is that blocked font request); no screen-reader pass; the clip checker does not open the list or step the guide.
