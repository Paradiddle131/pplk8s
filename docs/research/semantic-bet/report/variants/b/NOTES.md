# Variant B: the analyst's console

Direction: one dense, working screen of linked views (impeccable's Operate mode) where every estimate is drawn the same way, as a mean tick on its 95% interval, so uncertainty reads before the number does.
The identity lives in precise details: a slate-blue control rail, Archivo set condensed for the data and wide for the takeaways, tabular figures, state shown in form (hollow mark plus dashed interval plus dashed chip for a partial pass; filled `decides`, outlined `check`, dashed `descriptive` badges).

## Views and why each form fits its data

- **Decision map (first screen):** a grouped table, rows by cost-ladder step then setup then model, because the question is a lookup across setup × model × question group; inline interval glyphs carry accuracy and confident-wrong, heat cells carry per-group share right (faded under 10 cases), and an "Against the managed best" column shows the rule's paired verdict (tie, below, worth building).
  Above it, two templated lists: what the evidence shows (deciding pair, Claude check, why) and what would move the picture (partial passes, pairs not yet run on the free model or on Claude, `compile_query`).
- **Accuracy against confident-wrong:** a scatter with interval crosshairs (both bootstrap intervals), y inverted so the best corner is top right; color is the setup's kind, shape the model family; the managed best is a dashed reference line.
- **Covered against uncovered:** a strip plot, one row per question group, one lane per setup kind; per-group shares have no interval in the data, so a dot per setup is honest and the MetricFlow lane's drop on uncovered is visible at a glance.
- **Cost ladder:** a forest plot of points over `native-bare`, rows cheapest to most custom in the owner's words, the floor's own interval as a grey band, the unmeasurable `compile_query` rung drawn as an empty dashed row, Claude dollars per 100 runs in the right margin.
- **Detail pane:** the selected setup's intervals, outcomes as a segmented bar, the paired result with its role, spend per 100 runs and per right answer, tool-use counts from the logs, and two example answers (a right one, preferably hidden-rule, and its most frequent failure) with the first tool call.
- Controls: set (frozen/hard), model family (filters every view), question group (highlights a column and switches the ladder to that group's share). Click or Enter on any row or mark selects it in all five views.

## Rebuild

`python3 build.py results.json` (in the repo, logs and question text are found beside it), or `python3 build.py ../results.snapshot.json --repo /home/user/pplk8s` here; `template.html` must sit beside `build.py`.
Every number in prose is a template over the embedded data; spend is matched to setups by parsing the pass names.

## What the full build would add

- The metric-type coverage matrix, the Lightdash and `compile_query` explainers, tool-use evidence for the local arms (their log has no `calls`), and a glossary.
- Sortable columns, a URL hash for the selection, a static `embedded_html` twin with SVG `<title>` hovers for GitHub.
- The power check and the free-trial end date moved into `results.json` (they are cited constants in `build.py` today).

## What I would ask the owner

1. Should the map's rows be one per setup (best model shown, others on expand) so the first screen fits without scrolling, or keep every setup × model row visible?
2. Is "worth building" by the rule on Claude only (native-mcp on Sonnet, frozen) the headline, or must it wait for the free model's native-mcp pass?
3. Should the Gemini variants with one case (fast, thinking) stay visible, or be folded until they have a full pass?

## Known weakness

The map is long (about 30 rows on the frozen set), so at 1280 × 800 the first screen shows the takeaway, readings and only the cheapest rungs; on a phone the table scrolls sideways inside its panel.
