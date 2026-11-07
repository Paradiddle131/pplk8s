# Results audit of every logged run (pplk8s, issue #382)

A blind audit of the eval CASES just finished: /tmp/claude-0/hv2/audit/frozen-a.md, frozen-b.md, hard-v1.md and hard-v2-new.md. Read all four first.
Your job is the RUNS: find logged runs whose recorded outcome misleads, and measure how often each case-level risk the auditors found actually happened.
Apply every check to every arm and model alike; never look for faults in one arm only.

## Inputs (read-only; edit no repo file)
- Logs: /home/user/pplk8s/docs/research/semantic-bet/eval-*.jsonl. Rows are runs: {arm?, model, case, run, at, outcome, turns:[{text, outcome, ...}]}; a per-arm log's arm comes from its file name (`eval-<arm>.jsonl` is the frozen set, `eval-hard-<arm>.jsonl` v1, `eval-hard-v2-<arm>.jsonl` hard-v2). `eval-local.jsonl` holds several arms.
  Rows with `carried_from` in `eval-hard-v2-*` are copies of v1 rows: count them once (under v1) and note it.
- judge.jsonl: blind-judge verdicts that change a turn's outcome on read. Logged outcomes are the code's at logging time; the code rescored all logs on read later, so compute the current outcome yourself as below rather than trusting the stored one.
- Scorer: services/semantic-agent/src/semantic_agent/evaluation.py (`carries`, `expected_numbers`, `_stated`, DATES, NUMBER) and bet_rule.py, bet_eval.py (`recode`, `apply_verdicts`). Use them: `cd /home/user/pplk8s/services/semantic-agent && uv run python -c ...`. `bet_eval.judged_logs(bet_eval.load_set(name))` gives every run of a set scored as the report scores it now; `evaluation.expected_numbers` needs the warehouse (dbt_dev is up: docker exec pplk8s-warehouse-1 psql ...), or take each case's expected values by running its expected_sql.
- The set files: services/semantic-agent/evals/semantic_bet.yaml, semantic_bet_hard.yaml, semantic_bet_hard_v2.yaml.

## Checks (all runs, all arms)
1. Infrastructure failures scored as answers: answers or turns showing a tool or connection error, refused query, quota, timeout, permission or audit-row failure, empty text, a `failure` field. Each one is a run to redact and rerun. Say which arm, model and pass.
2. False right (chance carries): for every turn the scorer marks right, find which stated number matched an expected one. Decide whether the answer's actual answer to the question is that number, or whether it matched incidentally: a date or day, an ID, a count of something else, a number in a list, a number from the question, or the answer's main figure differing from the expected one.
   Do this mechanically where you can (the matched number is not the answer's headline figure, or the answer states another candidate figure first), then read every flagged turn yourself and classify it: genuine / chance / unclear.
   Cover at least every case the four audits flag with a scorer risk, plus any case whose expected number is a whole number of 40 or less.
3. False not-right (scorer misses): turns scored wrong, confident-wrong or declined whose answer states the expected number in a form the parser misses (a whole percent such as 17% for 16.67%, a locale format, words, "6 days" for 6.0833 when the question asked for days). Classify each: genuine miss / scorer miss / unclear.
4. Ambiguous turns: for the `ambiguous` turns of every set, whether the answer really asked which meaning or gave every meaning, or silently picked one and ended with an unrelated question (the audits found `ASKS_WHICH` loose).
5. Duplicates: two rows with the same arm, model, case and run number in one log (a resumed pass written twice); say which one each read keeps.
6. Runs of cases the case audits call defects of class expected_sql, readings or fixture: count them per arm, nothing else.

## Output
/tmp/claude-0/hv2/audit/results.md:
- A summary table per check: count of runs flagged and confirmed, per arm and model.
- Per case: right runs, chance carries, scorer misses. This is the evidence of whether each scorer-risk case actually misled.
- A list of run keys to redact (arm, model, case, run, at, set, reason, a quote of the evidence).
  Only runs whose recorded outcome is misleading because of the TEST or the INFRASTRUCTURE, never because an agent answered badly.
- What changes in each arm's accuracy and confident-wrong rate per set if the confirmed redactions apply (recompute with the overlay idea: drop those runs).
- Your recommendation, for each scorer risk the audits raised: retire the case, or keep it because no run actually misled, or fix the scorer for every arm (say how).
Also write the run keys to /tmp/claude-0/hv2/audit/redact-candidates.jsonl, one JSON row each: {"kind":"run","arm","model","case","run","at","set","reason","evidence"}.
End your reply with the headline counts and the two paths.
