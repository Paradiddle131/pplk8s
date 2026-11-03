# The scorer learns the decline and scope-caveat wordings the logs show (#367)

Question: [#366](../../../../../../issues/366) and [#363](../../../../../../issues/363) found answers the code scores confident-wrong that are declines or scope caveats when read: does teaching the code those wordings move any arm's numbers, and what do the new judge candidates get?

## What was changed

- [`bet_rule.py`](../../../../services/semantic-agent/src/semantic_agent/bet_rule.py), a dated change in [`RULE.md`](../RULE.md) § Changes since freezing; the set's `hedges` list is untouched.
  - `NOT_IN_DATA` gains the two declines #366's judge found the code missing, as `not tracked` and `no … column|table|field … to compute|calculate|determine` (within a sentence).
    A figure beside them is now wrong (hedged) by the code, and an answer with no number declined.
  - `HEDGE_LIKE` (the judge's candidates) gains the scope caveats: `cannot|can't|unable to split|filter|isolate|break`, `covers all`, `not broken down|out`.
    The code still cannot tell such a caveat from a plain statement, so these turns stay confident-wrong for the code and go to the judge.
- [`bet_eval.py`](../../../../services/semantic-agent/src/semantic_agent/bet_eval.py): `recode` scores every log's turns on read from their text under the current wordings, keeping from the log whether a turn was right, so the change reaches the live arms' logs without rewriting a line, as #358 applies the judge's verdicts.
  - It needs no warehouse, and it is exact for wordings that widen (every change so far): a test checks it agrees with `rescore` from the expected numbers.
  - A moved turn keeps the logged outcome as `logged`; `eval.md` counts the moved turns per arm, from and to.
  - `judged_logs`, `--judge` and the local report all read through it.
- `probes/328_mcp_live.py` wrote `eval.md` from the raw logs, without the judge's verdicts (an omission since #358): it now writes it from `judged_logs`, as `bet_eval` does.
- Tests: each quoted answer verbatim (`tests/test_bet_rule.py`: the two declines beside a figure are wrong, two "not tracked" answers without a number are declined, the three Lightdash caveats and a "not broken down by" answer are judge candidates and still confident-wrong for the code, a plain wider figure is not a candidate); on read (`tests/test_bet_eval.py`: a live log moved and never rewritten, agreement with `rescore`, right, planted, unanswered and unknown turns kept, a definition turn read, a scope caveat sent to the judge).

## What was run

- 2026-11-03T20:51Z (`measured`): `dbt parse` and `scripts/build_catalog.py` in this worktree (the catalog `--rescore` reads for definitions; `make dbt-catalog`'s last step, which writes the warehouse, was skipped because other lanes held the warehouse lock shared; the file is byte-identical to the one another lane built on the same train head).
- 2026-11-03T20:51Z to 20:52Z (`measured`): `DBT_DBNAME=dbt_dev flock -s warehouse.lock uv run python -m semantic_agent.bet_eval --rescore` in `services/semantic-agent`: `eval-local.jsonl` came back byte-identical (no local turn holds a new wording), `eval-local.md` and `eval.md` rewritten.
- 2026-11-03T20:52Z to 20:53Z (`measured`): `flock openrouter.lock flock -s warehouse.lock uv run python -m semantic_agent.bet_eval --judge --requests 10`: 10 requests to `nvidia/nemotron-3-ultra-550b-a55b:free`, every pending verdict (`judge.jsonl` 44 → 54 lines).
- OpenRouter's free count (`measured`, `GET /api/v1/key`, field `data.free_model_daily_requests`): 932 of 1,000 used at 20:52Z before the pass and still 932 just after it at 20:53Z; 942 at 20:54Z: the count trails the requests by about a minute.

## What was observed

Turns the new decline wordings move on read (`measured`, every log; the judge had already decided each the same way, so no score moved):

| Arm | Case | Run | Logged | Now (code) | Judge before |
|---|---|---|---|---|---|
| `native-governed` | `bet_median_days_lead_to_booking` | 1 | confident-wrong | wrong | declined / declined, so wrong |
| `native-shaped` | `budget_left_end_of_september` | 3 | confident-wrong | wrong | declined / declined, so wrong |
| `native-shaped` | `outreach_reply_rate` | 3 | unclear | declined | declined / declined |
| `native-shaped` | `candidates_in_interview_as_of` | 3 | unclear | declined | declined / declined |

Three more turns hold "not tracked" and do not move: two right (`bet_wetter_day_nl_orders`, `native-graph` and `native-shaped` run 1: "weather data is not tracked … However, … 3 orders") and one already declined (`native-kc` `bet_sessions_per_order` run 2).

New judge candidates, all `custom-lightdash` run 1, judged 20:52Z to 20:53Z (`measured`):

| Case | Phrase | Verdicts | Now |
|---|---|---|---|
| `revenue_germany` | "cannot split" | declined / declined | wrong (a decline beside a number is a hedge) |
| `net_revenue_germany` | "cannot split", "covers all" | wrong / wrong | wrong |
| `candidates_in_interview_as_of` | "cannot filter" | wrong / wrong | wrong |
| `median_order_value` | (unclear, from #363) | declined / declined | declined |
| `cost_per_lead_search` | (unclear, from #363) | declined / declined | declined |

The judge (`judge.jsonl`), on `net_revenue_germany`: "This is a different number accompanied by a statement that it is not from the governed definition for the requested slice. VERDICT: wrong".

## What moved in the scores

- `custom-lightdash`'s confident-wrong rate on run 1 went from 17.1% to 9.8% (3 of its 7 confident-wrong turns), its accuracy unchanged at 58.5% (`measured`, `eval.md` before and after).
- Under the rule (§ The rule, 2), `custom-lightdash` against `native-context`: confident-wrong +0.171 [+0.073, +0.293] became +0.098 [+0.024, +0.195], still a difference; accuracy -0.378 [-0.537, -0.232] unchanged; still not worth building.
- No other arm's numbers moved: the four data-agent turns the code now decides were already moved the same way by the judge.
- Turns moved per arm (`measured`): `custom-lightdash` 3 confident-wrong to wrong (judge) and 2 unclear to declined (judge); `native-governed` 1 confident-wrong to wrong (code, was judge); `native-shaped` 1 confident-wrong to wrong and 2 unclear to declined (code, was judge); `baseline`, `custom-metricflow`, `native-context`, `native-graph`, `native-kc` none.
- `eval.md`'s google-data-agent section now reads "Turns the current wordings score otherwise than their log … 4"; "Turns judged" fell from 20 to 16 there, as the code took over four, and rose from 2 to 7 in the nemotron section.

## What it means for the verdict

- The rule's numbers no longer lean on a judge pass for the two quoted declines: the code scores them as the judge did.
- A semantic-layer arm whose tools lack a dimension (Lightdash's dropped entity joins) mostly says so: 3 of its 7 confident-wrong turns were scope caveats, so its confident-wrong gap to the managed best shrinks by 7.3 points but still excludes zero.
- `custom-metricflow`'s comparison and the managed best are unchanged.

## Still unknown

- Wordings outside both lists still stay confident-wrong unjudged: of the 68 confident-wrong turns now in the logs, 65 hold no listed or hedge-like phrase and 3 were judged confident-wrong ("based on", #366), but no human read them all.
- The curly apostrophe: answered by [#368](../../../../../../issues/368), § Typographic apostrophes below.
- Turns logged after this branch's head need `--judge` again: 2 requests per new candidate.

## Typographic apostrophes (#368)

Question: `DECLINE`, `NOT_IN_DATA` and `HEDGE_LIKE` spell the apostrophe as ASCII `'`; does a "can’t" or "doesn’t" in an answer escape them, and does folding it move any turn?

- Changed: `bet_rule.fold` reads ’ and ‘ as `'` before `declines`, the set's `hedges` and `unlisted_hedges` match (a dated line in [`RULE.md`](../RULE.md) § Changes since freezing; the set's `hedges` untouched).
  Every log is scored on read through it (`bet_eval.recode`, #367); the eval's own `answer_correct` keeps `DECLINE` unfolded, as `bet_rule` never changes how `evals/questions.yaml` is scored.
- Run 2026-11-03T21:01Z (`measured`, `bet_eval --report-only` and a read of every log): of every turn in the seven logs, one answer holds a typographic apostrophe: `custom-lightdash` `cost_per_lead_search` run 1, "… so I can’t isolate search‑campaign lead cost …".
  Folded, it holds the hedge-like "can't isolate", which matters only beside a figure; it gives no number, and "can't isolate" is a scope caveat, not a decline wording, so the code still leaves it unclear and the judge's cached declined / declined stands (its answer hash is unchanged).
- Moved: no turn, on any arm; `eval.md` still reads "Turns the current wordings score otherwise than their log …: 4" (#367's four), and no new judge candidate (0 requests; the free count read 942 of 1,000 at 21:01Z).
- Still unknown: the same answer's curly quotes ("no “cost per lead” metric") keep `DECLINE`'s `no (such |word )metric` from matching a quoted multi-word name; no logged turn's outcome depends on it today.

## Sources

- `docs/research/semantic-bet/eval-*.jsonl`, `judge.jsonl` and `eval.md` at this branch's head (`measured`).
- [`findings/2026-11-03-366-unlisted-hedges.md`](2026-11-03-366-unlisted-hedges.md) and [`findings/2026-11-03-363-lightdash-numbers.md`](2026-11-03-363-lightdash-numbers.md) for the quoted answers.
