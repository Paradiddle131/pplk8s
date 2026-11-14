# Variant C: every answer visible

Direction: no bar, no headline percentage stands alone; every logged run (5,960 on the frozen set, 2,579 on the hard set) is one square, coloured and shaped by outcome, so the reader counts the evidence behind each number.
The aesthetic risk is density on a "plate reader" ground: thousands of 4–9 px wells in one cool, clinical field, with an expanded Archivo headline as the only loud element, and summary statistics set small beside the units.

## Views and why each form fits

- **Decision map (first screen):** setups × question types; each cell is a unit chart in which one column of three squares is one question (k = 3 runs), sorted best first so the blue mass reads as a countable bar, unrun runs drawn as faint dots.
  The question types are partitioned (each question in one column), so a row holds every run exactly once; results.json's overlapping `covered` share shows on hover.
  Beside the units: the share right per cell, then results.json's accuracy and confident-wrong as dot-and-interval strips (hollow dot = partial pass, grey tick = managed best), then $ per 100 runs.
  The title is a template: ADK on MetricFlow on the free model, tested per column against the managed best (paired bootstrap), says "ties" only where the interval holds zero.
- **Where the evidence stands / what would move it:** templated from step 2, step 3, managed best, partial and stub passes, the power check, and `compile_query`.
- **Cost ladder:** the same unit plates, but every rung keeps each question in the same x position (ordered by how the bare agent did), so a question's squares visibly turn from red to blue as context is added; hovering one column highlights it on every rung and prints the question.
  The right strip is each rung's accuracy minus the floor, paired by question, with a 95% interval; the `compile_query` rung is listed as unmeasured.
- **Run drawer:** click any square (or arrow keys plus Enter) for the question, every turn's answer, its outcome, the judge's verdicts when they decided it, and the tool calls with their SQL.
  Clicking a setup name opens its row: what it is, reach, tallies, cost, against the floor, and the rule's step 2 pair.

Outcome palette validated with the dataviz validator (all-pairs, light and dark); shape repeats colour (filled, hollow, half-filled, dotted ring, oversized) for colour-blind readers.

## How it is built

`python3 build.py results.json [logs_dir] [sets_dir]` reads results.json, the `eval-*.jsonl` logs, `judge.jsonl`, and the two set files (question text and groups), and writes `index.html` from `template.html`.
Runs are rescored as `bet_eval` does on read (the judge's two verdicts applied): 2 of 8,539 drawn runs differ from results.json, and the page says so.
Intervals per cell and against the floor are computed here (seeded bootstrap over questions) and labelled as such.

## A full build would add

The equal-reach table ("What this setup is" with context, tables, tools per row), tool-use counts from `calls` (search_entries, lookup_context, metric tools against own SQL), the metric-type coverage matrix, the Lightdash and `compile_query` explainers, a table view of the map, method notes and the glossary.

## Questions for the owner

- Should the eval write each run's scored outcome (for example a `runs` array in results.json), so the report never replays the scorer? That is the framework-native fix for the 2-run gap.
- Is the 5.7 MB page (every answer and trimmed SQL embedded) acceptable, or should answers move to a supporting file?

## Known weakness

At 400 px the map's 96 question columns need a horizontal scroll inside the plate (row labels stay pinned), and 4 px squares are hard to hit by touch; the drawer and the keyboard path work, but the phone reads as a preview, not a working view.
