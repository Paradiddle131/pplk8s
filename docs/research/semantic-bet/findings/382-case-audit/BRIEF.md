# Blind defect audit of eval cases (pplk8s, issue #382)

You audit eval cases for defects in the TEST ITSELF, blind to how any agent did on them.

## Hard rules (blindness)
- Do NOT open, grep or cat any of these: `docs/research/semantic-bet/eval*.md`, `docs/research/semantic-bet/eval-*.jsonl`, `docs/research/semantic-bet/judge.jsonl`, `docs/research/semantic-bet/results.json`, anything under `docs/research/semantic-bet/findings/`, `docs/research/semantic-bet/report/`, `ledger.d/`, `LEDGER.md`, GitHub issues or PRs. They hold agents' results; reading them breaks the audit.
- You may read: `docs/research/semantic-bet/RULE.md` (definitions; it holds no results), the set files in `services/semantic-agent/evals/`, `dbt/dev/fixture.sql`, `dbt/dev/fixture_weeks.sql`, `dbt/models/**`, `dbt/target/catalog/agent.json` (the semantic layer's metrics, to check coverage labels), and the scorer: `services/semantic-agent/src/semantic_agent/evaluation.py` (`carries`, `expected_numbers`, `numbers_in`, the DATES regex) and `bet_rule.py`.
- You may query the fixture warehouse read-only: `docker exec pplk8s-warehouse-1 psql -U warehouse -d dbt_dev -At -c "<sql>"` (schemas silver, gold, exposed, governed, legacy). Never write to it.
- Do not edit any repo file. Write your report only to the output path you are given.

## What counts as a defect (RULE.md § Retiring a defective case)
1. `expected_sql`: the expected SQL answers a different question than the one asked, as a business user would mean it. Re-derive the answer independently from the question and the fixture, then compare numbers. Watch for cancelled orders, date ranges and boundaries, time zones (timestamps are UTC), ratio of sums vs mean of ratios, fiscal year (starts 1 February), week definitions (Monday to Sunday), "as of" dates, and distinct counts.
2. `readings`: the question has more than one reasonable reading giving different numbers, and the case accepts only one. An `ambiguous` turn that lists every meaning is fine.
3. `fixture`: the fixture cannot support the case. It has no rows, or the answer is fixed by how the synthetic data was built (0%, 100%, a constant ratio).
4. `scorer`: the scorer misjudges answers to it. The eval marks a turn right when any number stated in the answer is within 0.006 of an expected number, or equals it rounded to the decimals the answer states (a rate also matches ×100). So flag:
   - small or common expected numbers that a wrong answer would likely carry by chance (counts like 5, 9, 10, 20, 31, 40; a number equal to a day, month or year in the question; a number the question itself contains; a total of rows a typical answer would also state);
   - expected values the parser cannot match in a normal right answer (very small rates, negative numbers stated as "fell by X").
5. `label`: its group label is wrong. `covered`: one metric query of the semantic layer, with its dimensions and filters, answers it. `composable` (hard-v2 only): arithmetic over at most three metric query results does. `uncovered`: neither. A `trap`'s `naive_sql` must be the obvious query and must give another number.
   A wrong label is a labelling defect, fixed by relabelling, not retirement.

NOT defects: a question being hard, every agent likely getting it right or wrong, a table some agent might not reach (a reach limit, like the weather questions: note it as `reach`, verdict ok), or a definition you would have chosen differently when the question states its own.

## Output
A markdown file at your output path:
- One table row per case: `case | verdict (ok / defect / doubt) | category | evidence (the SQL you ran and its numbers, the reading, or the scorer risk) | proposed fix (none / retire / relabel to X / corrected case in a later version)`.
- Below the table, a short list of the defects and doubts in order of severity.
Be strict but fair. "doubt" means you could not settle it; say what would. End your reply with the counts per verdict and the path you wrote.
