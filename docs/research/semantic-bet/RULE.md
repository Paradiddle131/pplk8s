# The bet's eval rule

Frozen 2026-11-03 by #325, before any arm is scored.
It fixes the question set, the arms, how a run is scored and the rule that turns scores into the verdict, so the eval cannot be bent toward the answer we hope for.
The set is [`services/semantic-agent/evals/semantic_bet.yaml`](../../../services/semantic-agent/evals/semantic_bet.yaml); its SHA-256 at freezing is in [the finding](findings/2026-11-03-325-frozen-eval.md).

## What freezing means

- From the first scored run on, nobody edits the set's questions, expected SQL or groups, this rubric or this rule.
- A defect found later (an expected SQL that answers another question, a fixture row that makes a question unanswerable) gets a new dated set beside this one; the report scores both and says which it decides on and why.
- A new arm may join later (Claude variants, an arm a register question adds); it is scored on this set under this rule, and the arms already scored are not rerun to suit it.

## The set

| Group | What it holds | Why |
|---|---|---|
| `covered` | questions a metric of the semantic layer answers | where a semantic layer should win |
| `trap` | covered questions whose obvious SQL over the trusted tables gives another number (the set's `naive_sql` per question, checked to differ on the fixture) | definitions the schema cannot show (#314) |
| `distractor` | covered questions where a legacy table in reach gives another number (`legacy.*`, #185) | the wrong-table failure |
| `uncovered` | questions no metric covers, written blind from the business description (the finding says how) | where a semantic layer refuses and SQL can still answer |
| `conversation` | follow-ups, "how was that computed", ambiguous terms | what a chat adds |
| `planted` | rows holding instructions | safety, reported, never deciding |

At least 30% of the cases are `uncovered`; a case may be in `trap` or `distractor` and `covered` at once.
Every case keeps `questions.yaml`'s shape, so `services/semantic-agent`'s eval can load it; the groups sit in the file's `groups` map.

2026-11-03, [#356](../../../../../issues/356): a second set, [`services/semantic-agent/evals/semantic_bet_hard.yaml`](../../../services/semantic-agent/evals/semantic_bet_hard.yaml) (43 cases, 44% `uncovered`; SHA-256 in [its finding](findings/2026-11-03-356-hard-set.md)), is an addition the owner asked for, not a correction: "were the agents asked such hard questions, difficult to measure and easy to fail due to the complexity of the business query, as well as the lack of knowledge around the terms? If not, I would really like to … add hard queries and measure accordingly" (owner, 2026-11-03).
It is scored beside the first set under this same rule (outcomes, the two numbers, the paired comparison, the ladder), each set reported on its own, and it is frozen from now on, before any arm runs on it, as § What freezing means says of the first.

## The arms

The arms of [the register](README.md#the-arms), each built by its own issue: `native-context`, `native-governed`, `native-kc`, `native-shaped`, `native-graph`, `native-mcp`, `custom-metricflow`, `custom-toolbox`, and `baseline` (the reference, text-to-SQL that reads the generated docs).
Every arm that writes SQL is given the `legacy` schema beside the trusted layers (#185), with the descriptions it already carries ("replaced by …"); an arm that cannot read it (`custom-metricflow`) says so in the report.
An arm is scored with each model it is run with; the decision compares arms on the same model.

## Scoring a run

Each case is asked `k = 3` times per arm and model (#184), each run in a fresh session, the turns of a conversation in one session.
Each turn of a run gets one outcome:

- **right**: the answer carries an expected number in one of the forms the eval accepts today (`evaluation.py`: within its tolerance, a rate also as a percentage), or for a `define` turn quotes the definitions, or for an `ambiguous` turn asks which meaning or gives every number.
- **declined**: no number, and it says it cannot answer, that nothing defines it, or asks a question back.
- **confident-wrong**: a number outside tolerance, with no statement in the same answer that it is uncertain, partial, an estimate, or not from governed definitions (a decline in the same answer, "no metric covers it, but …", is such a statement).
- **wrong**: any other answer (a number outside tolerance with such a statement, or no number and no decline).

The code decides where it can ([`semantic_agent/bet_rule.py`](../../../services/semantic-agent/src/semantic_agent/bet_rule.py), #340): the number parses (the eval's own parser), and a hedge is one of the phrases in the set's `hedges` list, matched case-insensitively.
Where the code cannot decide (no number parses but the answer is not a decline, or a hedge is phrased outside the list), a blind judge decides twice: a free model shown the question, the expected number and the answer, never the arm; two equal verdicts stand, two different ones make the turn **unclear**, counted as wrong and listed in the report.
A run of a case is right when every turn is right; it is confident-wrong when any turn is.

On an `uncovered` case, only the number is right: a decline is not right, and not confident-wrong either.
So a semantic layer that refuses honestly loses accuracy there and keeps its confident-wrong rate, and the report shows both.

## The two numbers per arm

- **Accuracy:** the mean over cases of the share of an arm's runs that are right.
- **Confident-wrong rate:** the mean over cases of the share of its runs that are confident-wrong.
- Reported beside them, never deciding: pass^3 (cases right in all three runs), each group's accuracy, the requests spent.

## Comparing two arms

- Paired by case: per case, arm B's share right minus arm A's (and the same for confident-wrong).
- A percentile bootstrap 95% interval of the mean difference, resampling cases, 10,000 resamples, seed 325.
- An interval that excludes zero is a difference; one that includes zero is **no difference**.
- With the set's size and three runs, the smallest accuracy difference this detects four times in five is in the finding (the power check); a smaller true difference will mostly read as no difference, and the report says so beside every tie.

## The cost ladder (a tie goes to the cheaper rung)

1. A Google-managed agent with configuration only: `native-context`, `native-kc`.
2. A managed agent over warehouse objects we generate and keep: `native-governed`, `native-shaped`, `native-graph`.
3. Our agent on managed or generated tools: `native-mcp`, `custom-toolbox`.
4. Our agent on our own semantic-layer server: `custom-metricflow`.

Within a rung, the arm with the fewer moving parts named in its finding wins a tie.

## The rule

1. Take the best arm on rung 1 or 2 by accuracy (the **managed best**).
2. An arm on rung 3 or 4 is worth building only if, against the managed best, its accuracy difference excludes zero above it, or its accuracy shows no difference and its confident-wrong rate's difference excludes zero below it.
3. Otherwise the verdict adopts the cheapest arm that shows no accuracy difference from the best arm overall, and names what the others would add.
4. The groups explain the verdict (where an arm wins or loses), and never overturn it: a win on `trap` alone is a reason the report names, not a rule.
5. Every comparison the report shows besides these is descriptive.
