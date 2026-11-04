# Variant A: the research memo a statistician would sign

Direction: a long-form memo in a scientific-paper register (abstract, numbered figures whose titles are the sentence each proves, method and glossary at the end), set in STIX Two Text, the face of scientific publishing, with Barlow Semi Condensed for instrument-style chart labels.
Its world is the lab notebook: cool graph-paper ground, blue-black ink, plots drawn on a faint millimetre grid, intervals everywhere, and colour spent only on how a setup reaches the data.

## Views and why each form fits its data

- Figure 1, decision map: a setup by question-type matrix grouped by ladder rung (the setups are rows, the owner's question types are columns), one row per setup on the model that decides for it, other models behind "+ models".
  Shares are binned on one sequential ink ramp so the uncovered column's collapse reads at a glance; the best cell per column is boxed; overall accuracy and confident-wrong carry their intervals; cost sits in the last column. Four "what would move this" notes below it are computed from the data (partial passes, setups the free model has not run, the set's power, the pairs that clear the rule's bar).
- Figure 2, forest plot: the data are means with bootstrap intervals, so a two-panel interval dot plot (accuracy, confident-wrong) on shared rows is the native form; the managed best's interval is a shaded band, partial passes are dashed, marker shape gives the model (filled circle decides, open circle Claude check, square Gemini, diamond Claude Code).
- Figure 3, small-multiple slopes: three ordered question types per setup and model; a slope across covered, hidden-rule and uncovered shows the shape of the decisive split better than bars; one panel per way of reaching the data, with the managed best ghosted in each.
- Figure 4, ladder: rungs are ordered by cost, so rows run cheapest to most custom with each setup's accuracy as points over the floor (native-bare), its interval shifted by the floor's mean, the floor's own interval as a band, and a staircase for the best score reached so far; rung 8 (compile_query) is an empty dashed row.
- Hover or focus any row or line: interval bounds, cases and runs finished, outcomes, the paired difference against the managed best, cost with its source, and one example answer from the logs (first confident-wrong run, else first decline) with the tools it called.

## Build

`python3 build.py results.json [LOG_DIR]` reads results.json, optionally one example answer per setup from `LOG_DIR/eval-*.jsonl`, fills `template.html` and writes `index.html`; every sentence that cites a number is a template in `make_sentences`.
The only constants are non-measurements: plain descriptions, the ladder's wording, the Gemini free-trial end date and the power check (each with its source).

## What the full build would add

- The owner's other questions as further figures: tool-use evidence from `calls` (search_entries, lookup_context, metric tools against own SQL), Claude dollars per right answer and pass durations, the metric-type coverage matrix, Lightdash and compile_query in plain words, the blocked and unknown list.
- A static twin for the GitHub `embedded_html` artifact (same SVG, SVG `<title>` hover), the commit the build read, and per-group outcome splits (declined against wrong on uncovered) computed from the logs.

## Questions for the owner

- Should the decision map default to the frozen or the hard set, or show both side by side (it is a toggle now)?
- Is "one row per setup, on the deciding model" the right compression for the first screen, or do you want every model visible by default?
- The ladder mixes models (floor on Gemini, our setups on the free model or Claude): keep it, or restrict the ladder to Google's rungs and move ours to Figure 2 only?

## Known weakness

The decision map is wide (nine columns) and scrolls sideways inside its frame on a phone; its group shares carry no interval, so small groups (hidden-rule, conversation) can look more decisive than they are, which the caption states but the cells do not show.
