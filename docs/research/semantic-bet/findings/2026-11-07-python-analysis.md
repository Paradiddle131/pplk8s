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
