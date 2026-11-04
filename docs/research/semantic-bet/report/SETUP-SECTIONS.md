# Brief: a section that shows what each setup is

The report (`docs/research/semantic-bet/report/`, built by `build.py` from `template.html` and `../results.json`) compares about twenty "setups": ways of answering a business question over a shop's warehouse.
Today each setup is explained by one sentence in a table and in a tooltip.
The owner wants one more section at the bottom of the report that shows the setups themselves, so a reader understands them without reading every sentence: where each part runs, which agent asks, through which tools, over what semantic layer or context, with which tables in reach.
Two designers build this section in parallel with different approaches; the owner keeps one. You are one of them; your approach is at the end of your prompt.

## What to show (plain English, for someone who never sees the code)

For every setup: the asking agent (Google's managed BigQuery data agent, our ADK agent, a Claude Code subagent, a plain text-to-SQL agent), the model it runs on (Gemini inside Google's agent; the free model or Claude for ours), its tools or interfaces (Google's MCP servers, MetricFlow's tools `list_metrics` / `describe_metric` / `query_metrics`, generated Toolbox table-function tools, Lightdash's metric query API, plain SQL), the context it is given (nothing, Knowledge Catalog's import of the dbt metrics, column descriptions and a glossary, context generated from MetricFlow, verified example queries), and what it can reach (`silver` tables, governed tables, the `legacy` schema, a property graph, table functions).
Highlight how an ADK agent uses MetricFlow: it lists the metrics, reads one metric's definition and dimensions, and asks MetricFlow to compute; MetricFlow writes the SQL against the warehouse; the agent never writes SQL. Contrast it with the data agents, which write their own SQL from whatever context they hold.
Group setups by the cost ladder's rungs (the report's `ladder` in the embedded data: bare data agent; plus catalog context; plus context generated from MetricFlow; plus warehouse objects; our agent on Google's MCP servers or generated tools; our agent on a semantic-layer server; the hybrid; the reference baseline), so the differences inside a rung (for example `native-governed`, `native-shaped`, `native-graph`) read as small variations of one shape.

Read for the facts, in order (read-only):
1. `docs/research/semantic-bet/README.md` (the register of arms) and `docs/research/semantic-bet/RULE.md` (the ladder).
2. The report's own one-line descriptions: `desc` in `build.py`.
3. The probes' docstrings in `docs/research/semantic-bet/probes/` (each says what its setup is given: `354_data_agent.py`, `327_kc_agent.py`, `329_shaped_agent.py`, `331_graph_agent.py`, `360_kc_max.py`, `372_bare_agent.py`, `328_mcp_agent.py`, `330_toolbox_agent.py`, `363_lightdash_agent.py`, `374_cc_agent.py`), and for our agents `services/semantic-agent/src/semantic_agent/` (`agent.py`, `hybrid.py`, `toolset_metricflow.py`) and `services/semantic-agent/src/sql_baseline/`.
4. Skim `docs/research/semantic-bet/findings/` only where a setup is still unclear.
Never invent a component; if a fact is unclear, leave it out.

## The house diagram style

Read `/home/user/claude-dotfiles/skills/draw-architecture/SKILL.md` and its `REFERENCE.md`, and follow its style (boundaries, flows, labels, logos where it supplies them), adapted to the report's tokens below and made interactive. Don't run its scripts against the network; its `kit/` and `logos/` are local files you may read and inline.

## The contract with the report (fixed)

- Deliver exactly one file: `docs/research/semantic-bet/report/sections/<your-dir>/section.html`, a fragment holding one `<section>` with its own `<style>` (every selector scoped under your section's class) and `<script>` (one IIFE). The report's `build.py` inserts it near the bottom, before "Method, briefly". No other file of the report is yours to edit.
- Data: `window.REPORT` is the report's embedded data (`ladder`, `desc`, `familyLabel`, `sets`); read setup names, descriptions and rungs from it, so a setup added later appears with no edit. Static facts the data lacks (tools, reach, where things run) live in one small table at the top of your script, keyed by setup name, with a neutral fallback for an unknown setup. No scores or numbers: the section explains setups, the rest of the report measures them.
- Behaviour you get by markup alone: `data-setup="<arm>"` shows the setup's tooltip, `data-term="<term>"` a term's (glossary terms), both pinnable on click; any element with class `focusable` that contains `.mk` elements with `data-arm` gets hover-to-focus (the hovered setup stays strong, the rest dims). Start your script with `window.reportReady(() => { ... })`; re-render on the `report-theme` event if you draw to canvas.
- Style only through the page's tokens: `--paper`, `--paper-2`, `--ink`, `--ink-2`, `--ink-3`, `--rule`, `--grid`, `--grid-major`, `--da` (Google's data agents), `--gt` (our agent on Google's or generated tools), `--mf` (our agent on a semantic layer), `--ref` (reference), `--other`, `--cw`, and fonts `--serif`, `--label`, `--code`. Inline SVG or HTML; no new external scripts or fonts.
- Page rules: works at 400 px with no horizontal page scroll (a diagram may scroll inside its own container), both themes, visible keyboard focus, `prefers-reduced-motion` respected, complete at rest, no text overlapping other text.
- Content rules: plain words; no issue or PR numbers, no file names, no costs, nothing about how the research was run.

## Check before handing back

- The report builds and shows your section: `cd docs/research/semantic-bet/report && python3 build.py ../results.json`. If the report's `<!--SECTIONS-->` include isn't there yet (another designer is adding it in parallel), test with a copy: in your own scratch directory, paste your fragment into a copy of the built `index.html` just before the "Method, briefly" heading, with a two-line shim defining `window.REPORT` from the page's `D` and `window.reportReady = (f) => f()`.
- Playwright at 1280 and 400 px, light and dark: no console errors, no horizontal page scroll, no overlapping text inside your section (check every visible text box's client rect against its neighbours), and screenshots `section-desktop.png`, `section-phone.png`, `section-focus.png` (one setup highlighted) beside your `section.html`.
- Reply with the path, what you checked, and three lines on what your approach does better than a table.
- Don't touch git. Time box about 60 minutes.
