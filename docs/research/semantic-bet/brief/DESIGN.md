# Design: the Approaches page

World: enamel transit signage. The approaches are stations on one line, most native to most custom.
Mode: Operate (a table a person scans). One family: Atkinson Hyperlegible Next 400/600/700, tabular numerals.

## Tokens
| Token | Light | Dark | Job |
|---|---|---|---|
| --paper | #f4f6fa porcelain | #0a1430 midnight | page ground |
| --ink | #0d1b3e | #edf1f8 | every word and number (no muted text) |
| --band / --band-ink | #0d1b3e / #f4f6fa | #1b3373 / #f3f6fb | title band; chosen set = reversed plate |
| --line | #2447c9 | #86a4ff | route line, station rings, focus ring, selection |
| --ok / --warn / --bad | #0b7d4b / #b56f00 / #cf2a1f | #3fcf8e / #f2b23e / #ff6a5c | right / wrong / wrong and sure marks |
| --rule / --row | ink 16% / line 5% | ink 20% / line 8% | row hairlines / row hover |

## Rules
- Two data sizes: words 1rem, numbers 1.375rem bold; rank by weight and reversal, not size. Title 2rem.
- Marks: filled circle right, full-ink ring couldn't answer, amber circle wrong, scarlet diamond wrong and sure; the header marks are the only legend.
- Signature: the route line exists only in the native-to-custom order; sorting by a number lifts it (240 ms), "Approach" redraws it.
- Pointing at an outcome header lights that outcome's marks in every row (others to 14%).
- Definitions: one reversed bubble on hover or keyboard focus, 2.6 s on tap, Esc dismisses; screen readers get them via aria-describedby from a hidden block.
- Layout: fixed table above 75rem; below, stacked rows (max 40rem) with a 2x2 sort bar and marked numbers. Gutters max(16px, safe-area).
