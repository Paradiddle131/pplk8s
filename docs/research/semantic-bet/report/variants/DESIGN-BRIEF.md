# Design brief: three variants of the semantic-bet report

You are one of three designers working in parallel on the same task, each with a different direction (yours is at the end of your prompt).
The owner will compare the three side by side and pick one; the chosen one is then built in full.
So build a **convincing slice**, not the whole report: the first screen plus the central views below, on the real data, polished enough that the owner can judge look, feel and statistical honesty.

## The reader rule (owner, 2026-11-06; binding on every section and design)

The reader sees only the report: never our code base, issues, pull requests, designs, logs or files.
The owner: "The agents should always know that the reader will not see the code base, our issues, pull requests, our designs, etc. They are just looking at a report."
- Show only what a reader understands at a glance, with tooltips or a short explanation where a term needs one; every shown term has a glossary entry (`build.py` `TERMS`, checked by `tests/test_report_build.py`).
- Never on the page: hashes, freeze dates, set-version lineage ("v1", "v2", "supersedes", "not yet adopted", "new in a version"), retired questions in any form (no count, no reason, no list, not even beside a verdict: owner, 2026-11-06, RULE.md § Changes since freezing), pass or run bookkeeping, issue or PR numbers, file names, the owner's decisions, or filters over such fields ("Any / Scored / Retired / New in a version").
- A set is named by what it holds; a difference between two sets is explained only where a reader needs it to read a number.
- These facts stay in RULE.md, the findings and the data (`results.json`); `build.py` keeps them out of the page's visible text and its embedded data.

## The subject

A research track asked: for a business user asking questions about a shop's warehouse, which agent setup gives the right number, and which gives a confidently wrong one?
Setups ("arms") range from Google's managed BigQuery data agent with more or less context, to custom ADK agents on MetricFlow (dbt's semantic layer), Google's MCP servers, a Toolbox, Lightdash, a hybrid, and a plain text-to-SQL baseline.
Models: a free OpenRouter model (the deciding one), Claude Haiku/Sonnet/Opus (the check), Gemini variants inside Google's data agents, and Claude Code subagents (a different harness).
Two question sets: `frozen` (96 cases) and `hard` (43 cases); each case run up to k = 3 times; question groups `covered` (a metric answers it), `trap` (call it "hidden-rule questions": the obvious SQL is wrong because a business rule isn't visible in the table), `uncovered` (no metric answers it), `conversation` (multi-turn), `planted` (instruction-like text in the data), `distractor`.
Outcomes per run: right, declined, wrong, confident-wrong (a wrong number stated without hedging), unclear.

Read, in this order (read-only; never edit anything under /home/user):
1. `BRIEF.md` beside this file: the owner's questions, form and data rules. Follow it. The newest owner hints are its section "Hints from the owner, 2026-11-04T20:15Z".
2. `results.snapshot.json` beside this file: the only data source (a copy of `docs/research/semantic-bet/results.json`). Each `arms[]` row is setup × model × set: `accuracy` and `confident_wrong` are `[mean, lo95, hi95]` (percentile bootstrap over cases), `groups` is `{group: [share right, cases]}`, `cases`/`of_cases`/`runs` mark partial passes, `outcomes` counts runs, `rung` is the cost-ladder rung, `harness`/`session` say how it ran. `step_two` is each custom setup's difference against the managed best (`worth`), `managed_best` and `step_three` name the best managed setups, `claude_spend_by_pass` is dollars.
3. `/home/user/pplk8s/docs/research/semantic-bet/RULE.md` (the decision rule and cost ladder), `README.md` beside it (the question register), `eval.md` beside it (the current tables as text), and skim `findings/` for the meaning of setups you don't understand. The per-run logs `eval-*.jsonl` hold every answer and tool call (`turns[].calls`); you may read them for an example answer or for tool-use evidence.

## What your slice must contain

1. **A decision map as the first screen** (owner's pick): at a glance, which setup wins on which question type, at what cost, and what would change the picture. It states the evidence as of a date, never a closing verdict (owner: "I don't want to rush towards having such a verdict in a way that we would close the entire case").
2. **Accuracy against confident-wrong per setup and model, with intervals**, showing where the ADK agent on MetricFlow stands next to the native setups; partial passes visibly marked.
3. **The covered-vs-uncovered split by question group** (the decisive split: MetricFlow ties the best native setups on covered and hidden-rule questions and loses on uncovered ones, where it declines by design).
4. **The cost ladder**: cheapest to most custom setup, each rung's score as an increment over the floor (`native-bare`, tables only).
5. Hover/click details (interval bounds, runs, cases, model, cost, an example answer) where they help.
Every visual has a takeaway title (the sentence it proves), a legend, labelled axes and units; every results table has a "What this setup is" column in plain words.

## Hard constraints

- **Rebuildable from data.** Write `build.py` (Python 3 standard library only) that reads `results.snapshot.json` (path as its first argument) and writes `index.html`, embedding the data as JSON; no number is typed by hand into prose or markup. A new pass must only need `python3 build.py results.json` and a republish. Takeaway sentences that cite numbers are templates over the data.
- **The page is a claude.ai artifact**: write page content only (no `<!doctype>`, `<html>`, `<head>`, `<body>`), with a `<title>` (2–4 word name) and `<style>` at the top and `<meta name="claude:viewport-fit-sides" content="cover">`; scripts only from cdnjs.cloudflare.com, cdn.jsdelivr.net/npm/, or unpkg.com, each pinned to an exact version you already knew (UMD build, before the inline script using it); fonts only from Google Fonts with fallbacks; no fetch of anything; works at 400 px wide with no horizontal page scroll (side gutter `padding-left: max(16px, env(safe-area-inset-left, 0px))` and the same on the right); light and dark themes via tokens on `:root`, redefined under `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {…} }` and again under `:root[data-theme="dark"]`, with `body` given an explicit token background; complete at rest (nothing hidden waiting for scroll); visible keyboard focus; respect `prefers-reduced-motion`; no `window.print`, no download links.
- **Not AI slop.** Read and apply, before designing: the `frontend-design` skill (`/mnt/skills/public/frontend-design/SKILL.md`), the `dataviz` skill (invoke it with the Skill tool if you have it), and the `impeccable` skill (`../ext/impeccable/.claude/skills/impeccable/SKILL.md` relative to this file, then its `reference/craft-floor.md`, `reference/mode-read.md` or `reference/mode-operate.md` as your mode calls; read the markdown only, never run its `scripts/`). Avoid the clustered looks: cream + serif + terracotta, near-black + one acid accent, purple-blue gradient hero, Inter/Space Grotesk as the safe face, emoji markers, everything centered, identical rounded cards. Choose chart forms from the data's shape (intervals, shares per group, cost vs accuracy, a ladder), never by default.
- Statistically honest: intervals always shown with the mean, partial passes flagged, ties called ties, the free model marked "decides" and Claude "check", Gemini's data agents at $0.00 named as the free trial.
- Work only in your own directory `<this dir>/<your letter>/`; don't publish anything; don't touch git.
- Time box: about 60 minutes. Look at your rendered page once with Playwright (`require('playwright')`, `chromium.launch()`, wrap the file in a doctype skeleton for the screenshot) at 1280 px and 400 px, light and dark, fix what you see, then stop.

## Deliver in your directory

- `build.py`, `index.html` (built from the snapshot), two screenshots (`desktop.png`, `phone.png`).
- `NOTES.md`, at most 40 lines: your direction in two sentences; each view's chart form and why it fits that data's shape; what the full build would add; what you would ask the owner; one known weakness.
Your final message: the paths above and three lines of what makes your variant different.
