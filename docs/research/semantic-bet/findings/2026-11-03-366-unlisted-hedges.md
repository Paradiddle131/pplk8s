# Confident-wrong turns hedged outside the list, judged (#366)

Question: [`RULE.md`](../RULE.md) § Scoring a run sends two kinds of turn to the blind judge, but [#358](../../../../../../issues/358) sent only the first (no number and no decline).
A wrong number hedged in words outside the set's `hedges` list stayed confident-wrong, unjudged.
How many confident-wrong turns hold such a hedge, and does the judge move them?

## What was built

- [`bet_rule.py`](../../../../services/semantic-agent/src/semantic_agent/bet_rule.py): `HEDGE_LIKE`, a broad candidate list of hedge-like phrases, documented in the code.
  - It covers uncertainty words (approximately, roughly, around, may, might, could, likely, perhaps, probably, appears, seems, not sure, uncertain, unclear), assumptions (assum…, based on, treated as, taken as, interpret…, proxy, depending, if you) and scope notes (partial, incomplete, caveat, note that, please note, for reference, limited to, only includes).
  - It also covers "the data does not hold it" wordings ("not tracked", "not available", "no … column").
  - It is broad on purpose: a false match costs two judge requests, while a missed one leaves a hedged answer confident-wrong.
- `unlisted_hedges(text, hedges)` returns the phrases the answer holds that the set's list does not.
- `hedge_verdicts` combines the two verdicts on such a turn. The code already found the number outside tolerance, so the judge decides only whether it is hedged:
  - two `wrong` stand (hedged), and two `confident-wrong` stand (kept);
  - two `declined` become wrong, since a decline beside a number is a hedge under the rule;
  - two `right` contradict the parsed number, and two different verdicts disagree: both make the turn unclear, which counts as wrong and is listed.
- [`bet_eval.py`](../../../../services/semantic-agent/src/semantic_agent/bet_eval.py): `undecided_turns` gives the judge both kinds of turn, and `--judge` asks for both.
  - Verdicts are cached in `judge.jsonl` the way #358 caches them, keyed on the turn and its answer's hash.
  - `apply_verdicts` keeps the code's outcome as `coded` beside the verdicts.
  - `eval.md` counts the judged turns by kind, says how many confident-wrong turns the judge moved ("to wrong, hedged" and "to unclear"), and lists any candidate still awaiting the judge.
- Tests (`tests/test_bet_eval.py`) use a stub judge:
  - one turn moved from confident-wrong to wrong and one kept, with the counts in `eval.md`;
  - a plain wrong number with no hedge-like phrase never reaches the judge;
  - the five ways two verdicts combine on a hedged number.

## What was run

- 2026-11-03T20:30Z to 20:31Z (`measured`): `flock openrouter.lock flock -s warehouse.lock uv run python -m semantic_agent.bet_eval --judge --requests 40` in `services/semantic-agent`, `DBT_DBNAME=dbt_dev`, on the train's head `0a1f8d1` plus this change.
- An earlier attempt, started at 20:20Z with a 580 s timeout, waited on the OpenRouter lock the whole time and was killed before taking it: no request was sent and no verdict was written (`judge.jsonl` stayed at 32 lines).
- Requests spent: 12, all to `nvidia/nemotron-3-ultra-550b-a55b:free`, against a cap of 40.
- No new unclear turn was in the merged logs: the 16 from #358 were already cached, so the pass asked only for the 6 hedge candidates.
- Candidates (`measured`): 6 of the 67 confident-wrong turns across every log.

## What was observed

| Arm | Case | Run | Phrase outside the list | Verdicts | Now |
|---|---|---|---|---|---|
| `baseline` | `signups_september` | 1 | "Based on" | confident-wrong / confident-wrong | confident-wrong |
| `baseline` | `average_order_value` | 1 | "based on" | confident-wrong / confident-wrong | confident-wrong |
| `native-governed` | `lead_to_booking_rate` | 1 | "Note that" | wrong / wrong | wrong |
| `native-governed` | `bet_median_days_lead_to_booking` | 1 | "not tracked" | declined / declined | wrong |
| `native-shaped` | `average_order_value` | 3 | "based on" | confident-wrong / confident-wrong | confident-wrong |
| `native-shaped` | `budget_left_end_of_september` | 3 | "For reference" | declined / declined | wrong |

Raw excerpts (`measured`, `eval-*.jsonl` and `judge.jsonl`):

- `native-governed` `lead_to_booking_rate`: "The lead-to-booking rate was **33.3%** (0.333) on 1 October 2026 and **25.0%** (0.25) on 2 October 2026. Note that because lead-to-booking rate is non-additive …".
  The judge: "It gave numbers with a qualifying statement about non-additivity. VERDICT: wrong".
- `native-shaped` `budget_left_end_of_september`: "… there is no allocated **budget** column or budget table present in the schema to compute the remaining budget … For reference, the total ad spend …".
  The judge: "… cannot compute the remaining budget, providing only the total spend instead. This matches the definition of a declined response. VERDICT: declined".
- "based on 15 orders" is a source note, not a hedge: the judge kept all three such turns confident-wrong ("presents this figure definitively, without any qualification").

## What moved in the scores

- `native-governed`'s confident-wrong rate on run 1 went from 3.1% to 1.0% (`measured`, `eval.md` before and after; both of its candidates are run-1 turns).
  Its accuracy (72.9%) is unchanged, because a wrong turn is not right either.
- `native-shaped`'s moved turn is in run 3, which `eval.md`'s partial table (run 1) does not score yet; its table is unchanged.
- No other arm's numbers moved, and the rule's cross-model comparison is unchanged: the managed best is still `native-context`, and neither of its turns was a candidate.
- `eval.md` (`measured`):
  - google-data-agent section: "Turns judged: 20 (16 the code left unclear, 4 confident-wrong with a hedge outside the list); verdicts that stood: 20. Confident-wrong turns the judge moved: 3 of 4 (3 to wrong, hedged; 0 to unclear)."
  - nemotron section: "Confident-wrong turns the judge moved: 0 of 2".

## What it means for the verdict

- The set's `hedges` list misses few hedges in practice: 4 of 67 confident-wrong turns were hedged or declined in other words, all from data agents.
- The confident-wrong numbers the rule's step 2 uses now include the judge's view of these four turns.
- For `native-governed` the change is a third of its confident-wrong turns on run 1: an arm whose rate is small is the most sensitive to this.
- Two of the moved turns were declines in wordings neither the eval's `DECLINE` nor the bet's `NOT_IN_DATA` patterns catch ("not tracked or available", "no allocated budget column … to compute").
  The code still scores such a turn confident-wrong whenever it is not judged.

## Still unknown

- Hedges outside both the set's list and `HEDGE_LIKE` stay confident-wrong unjudged.
  The 61 confident-wrong turns without a candidate phrase read as plain statements of a number, but no human checked them.
- Whether the judge agrees with a human on these 6 turns: the agreement between its two verdicts is consistency, not correctness.
- Turns logged after `0a1f8d1` need `--judge` again on the merged logs: 2 requests for each new unclear turn or new hedge candidate.

## Sources

- `docs/research/semantic-bet/judge.jsonl`, `eval.md` and `eval-*.jsonl` at this branch's head (`measured`).
- OpenRouter's free request count, `GET /api/v1/key`: 844 of 1,000 used at 20:19Z and 932 at 20:33Z, the difference beyond these 12 being other lanes (`measured`).
