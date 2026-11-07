# Design: the Approaches page

World: enamel transit signage. The approaches are stations on one line, most native to most custom.
Mode: Operate (a table a person scans). One family: Atkinson Hyperlegible Next 400/600/700, tabular numerals.

## Tokens
| Token | Light | Dark | Job |
|---|---|---|---|
| --paper | #f4f6fa porcelain | #0a1430 midnight | page ground |
| --ink | #0d1b3e | #edf1f8 | every word and number (no muted text) |
| --line | #2447c9 | #86a4ff | route line, station rings, focus ring, selection |
| --ok / --warn / --bad | #0b7d4b / #b56f00 / #cf2a1f | #3fcf8e / #f2b23e / #ff6a5c | right / wrong / wrong and sure marks |
| --rule / --row | ink 16% / line 5% | ink 20% / line 8% | row hairlines / row hover |

## Rules
- Two data sizes: words 1rem, numbers 1.375rem bold; rank by weight and reversal, not size. Title 2rem.
- Marks: filled circle right, full-ink ring couldn't answer, amber circle wrong, scarlet diamond wrong and sure; the header marks are the only legend.
- Signature: the route line exists only in the native-to-custom order; sorting by a number lifts it (240 ms), "Approach" redraws it.
- Pointing at an outcome header, or focusing it from the keyboard, lights that outcome's marks in every row (others to 14%); leaving the header, Escape or a click elsewhere resets them, and sorting never lights them.
- Definitions: one reversed bubble on hover or keyboard focus, 2.6 s on tap, Esc dismisses; screen readers get them via aria-describedby from a hidden block.
- No title band: the page is two sections on the porcelain ground, Approaches and Takeaways, each under the same heading (1.375rem bold, route indent, 2px ink rule); the question-set switch sits beside the Approaches heading because it changes only that table; the page's h1 is for screen readers only.
- Layout: fixed table above 75rem; below, stacked rows (max 40rem) with a 2x2 sort bar and marked numbers. Gutters max(16px, safe-area).

## Takeaways
- Below the table, on the page ground: the heading at 1.375rem bold wears the table head's 2px ink rule and sits on the route indent.
- Each takeaway is one row, separated by the table's hairline: headline (1rem bold) and its one sentence on the left, one small picture on the right (30rem max); below 60rem the picture drops under the text.
- Every picture uses the table's 0-100 scale, its marks and its two data sizes; text stays HTML so it never scales with a drawing.
- Setup: two rails from 0 to 100, a green span between the lowest and highest score with filled circles at its ends, each end numbered under it (pushed apart when close); the end's name shows in the bubble.
- Rules: one bar pair per model, cheapest to priciest, under two column heads with the ink rule (questions a metric covers, questions none covers); the track is the whole 100, the green fill the share right.
- Definitions: one slope panel per setup, everyday questions to hard-to-interpret ones, right answers as a green line with circles and wrong-and-sure ones as a red line with diamonds; numbers are pushed apart when close; a two-mark key (Right, Wrong & sure) carries the column definitions in the bubble.
- Program: three bars, one per program, in the data's order.
- Words in a bubble wear a dotted underline in the line colour; screen readers get each picture as plain sentences (hidden text), its drawing hidden.
- No eyebrows, section numbers, cards, verdicts or muted text; no motion beyond the bubble.
