# Google's data agent with Python analysis on (`native-context-python`)

- Question: does turning on the data agent's Python analysis (`options.analysis.python.enabled`) change how often it is right or confidently wrong?
- Setup: `bet-context-python`, `bet-context`'s published context copied with that one switch on (read back: Python on, the 1 GiB byte cap and `MODEL_UNSPECIFIED` unchanged); RULE.md § Changes since freezing, 2026-11-07T10:20Z; the owner's go, 2026-11-07.
- Run: 2026-11-07, Google's model (free trial), one run a question; `make gcp-cost-check` $0.000010 (the known Artifact Registry line) and `make gcp-usage-check` ok before and after.

| Set | `native-context-python`, k = 1 | `native-context`, k = 3 |
|---|---|---|
| Extended hard set (55) | 92.7% right, 0.0% confident-wrong (51 right, 3 wrong, 1 unclear) | 92.7%, 0.0% |
| Frozen set (76) | 90.8% right, 2.6% confident-wrong (69 right, 2 confident-wrong, 5 unclear) | 87.3%, 3.9% |

- `measured`: in 131 runs the agent never took a Python step: every turn's calls are its generated SQL (and matched verified queries); the log names a Python step as `python_analysis`, and none appears.
- So the switch changed nothing it did; the frozen set's 3.5-point gap is one run against three, with overlapping intervals (90.8% [84.2, 96.1]), not the switch.
- Not run: k = 3 (RULE.md's entry runs it only when the first round shows a difference worth its runs; with no Python step taken there is none).
- For the work platform: enabling Python analysis on a data agent over well-described tables did not make its loop use Python for single-figure business questions; its figures still come from one SQL query a turn, so the controls that matter stay on SQL (byte caps, table reach, verified queries).
- Finished: 2026-11-07T10:52Z.

## Why no Python step (the owner's question, 2026-11-07)

- The setup is as intended: the published context reads `options.analysis.python.enabled: true` (GET), and the same context sent three ways gave the same stream: by reference (as the eval runs), by reference with `contextVersion: PUBLISHED`, inline in the chat request, and on `v1alpha`.
- Seven targeted chats (unlogged, raw streams in the session's scratch), none streamed an `analysis` message:
  - "Use Python to fit a linear trend to daily revenue for September 2026 and forecast 1 October": one SQL query (30 daily rows), then slope 5.1544, intercept 339.53, forecast €499.32, each exact against the warehouse's `regr_slope` / `regr_intercept`; the agent with Python off gave the same exact figures, so Gemini computed them from the 30 rows itself, though the answer says "Using Python".
  - An ARIMA forecast for October's first week: BigQuery's own forecast in SQL (two queries and a chart), no Python.
  - A Pearson correlation and z-score anomalies: SQL.
  - k-means clustering of customers by spend and orders (read-only SQL cannot fit a model), Python on and off: one SQL query, then the model clustered the 10 active customers itself.
- `stated` ([known limitations](https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/known-limitations), read 2026-11-07): Python-based reasoning handles "time complexities of up to `O(100k)` rows".
- Reading, `inferred`: the lab's warehouse is small (every result in these chats was at most a few dozen rows), so every result fits in the model's context and the agent computes there or pushes the work into BigQuery's SQL; Python would be the step for results too large to reason over, which this lab does not produce. Not separable here from "the switch is not honoured in this API surface"; both stay possible.
- So the 131 runs measured `native-context` again (a second sample of the same setup, which agrees with it), not Python analysis; the pass should have stopped after its first runs showed no Python step (now a rule in claude-dotfiles' cloud notes).
