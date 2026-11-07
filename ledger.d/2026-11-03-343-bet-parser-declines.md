## 2026-11-03 — Semantic track — the bet's parser stops calling declines confident-wrong (#343)

- Done: `bet_rule.py` leaves the question's own numbers out of what an answer states and reads "cannot be determined", "does not provide", "not separately" and the like as declines (the eval's `answer_correct` unchanged); `bet_eval.py --rescore` scores the log again from its text; three answers from the log, verbatim, in `tests/test_bet_rule.py`.
- Evidence: `make agent-test` 306 passed (5 new); the first pass rescored: the baseline's confident-wrong 19.1% to 12.8% (6 of 47, as read by hand), accuracy unchanged, no unclear turn left.
- Open: the blind judge for phrasings no list covers stays #333's.
