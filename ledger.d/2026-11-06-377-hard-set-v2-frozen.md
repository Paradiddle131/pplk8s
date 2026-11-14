## 2026-11-06 — Semantic track — hard-v2 drafted blind and frozen, proven hard by its naive SQL (#377)

- Done: `services/semantic-agent/evals/semantic_bet_hard_v2.yaml`, frozen 2026-11-06 before any arm ran on it, `supersedes: hard`: v1's 43 cases unchanged in what scores them, relabelled under v2's groups (14 of v1's 19 `uncovered` cases are `composable`, arithmetic over metric results), plus 15 new cases hard in SQL by RULE.md's rubric (1 `covered`, 6 `composable`, 8 `uncovered`).
  A separate Sonnet subagent drafted 105 questions blind in four rounds from #325's business description and the rubric, each round committed verbatim before it was used; 15 survived the fixture, the no-repeat rule and the small-number rule.
  The checker reports `composable` and runs every new case's naive SQL; a shape test holds the set; the finding has the SHA-256, the order with timestamps, every case's group, rubric kind, expected and naive number.
- Evidence: `probes/325_check_set.py` on a rebuilt dbt_dev → `cases 58`, `composable or uncovered 33 (56.9%)`, `naive SQL checked 21`, `failures 0`; `make agent-test` → `400 passed`; probes' ruff gates pass; SHA-256 `23b62532…84ff7`.
- Open: only one new `covered` case survived (the plan hoped for about 8): on this fixture the dashboard figures repeat the earlier sets; #378 next (bet_eval's `hard-v2`, carried runs, set families).
