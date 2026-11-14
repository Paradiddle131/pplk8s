# How often the Haiku judge is right (#429)

Written 2026-11-09T11:24Z; part of the fairness epic #424 (#425).

## The question

The blind judge (Claude Haiku through `claude -p`, #427) decides only the turns the scoring code cannot, but exactly the hard ones; how often is it right?

## What was run

- `probes/429_judge_calibration.py sample --n 60 --seed 429`: of the 605 turns Haiku decided with two equal verdicts (every set), 60 drawn stratified by its verdict and by setup family (an equal share per stratum, 15 strata): confident-wrong baseline 4, confident-wrong data-agent 4, confident-wrong google-tools 4, confident-wrong metricflow 4, declined data-agent 4, declined google-tools 4, declined metricflow 4, right baseline 4, right data-agent 4, right google-tools 4, right metricflow 4, wrong baseline 4, wrong data-agent 4, wrong google-tools 4, wrong metricflow 4.
- `label --model sonnet`: each sampled turn labelled once by a fresh `claude -p --model sonnet` process with no tool, no settings and no saved session, shown the same rubric prompt the judge was shown (the question, the expected number or definition, the answer) and never the setup's name or model; the labeller never saw Haiku's verdict.
- `report`: agreement by the judge's verdict and by family; files in `findings/429-judge-calibration/` (`sample.jsonl`, `labels.jsonl`).

## What was observed (measured)

- Agreement: **54 of 60 (90%)**.

| By | Agreement |
|---|---|
| verdict confident-wrong | 16 of 16 |
| verdict declined | 12 of 12 |
| verdict right | 15 of 16 |
| verdict wrong | 11 of 16 |
| family baseline | 11 of 12 |
| family data-agent | 15 of 16 |
| family google-tools | 14 of 16 |
| family metricflow | 14 of 16 |

Every disagreement, for the owner to settle (the labeller's reason, its last words):

- hard-v2 native-mcp hard_mqls_social_september run 1 turn 1: judge right, labeller declined. Labeller: "ar, but the answer disclaims it as the answer to the question. This is a judgment call. The answer's main stance is a decline, and the 40 is explicitly labeled as a different metric. VERDICT: declined"
- hard native-graph hard_roas_september run 3 turn 1: judge wrong, labeller confident-wrong. Labeller: "e differ substantially, and the answer states no uncertainty about the figures (it only explains its choice of revenue source). It is a different number presented confidently. VERDICT: confident-wrong"
- frozen custom-toolbox bet_top_country_september run 1 turn 1: judge wrong, labeller confident-wrong. Labeller: "expected one, and the answer states no uncertainty about it. The note on the period covered reads as a description of the data, not as a caveat that the figure is incomplete. VERDICT: confident-wrong"
- frozen cc-metricflow-compute bet_cart_to_checkout_minutes run 3 turn 1: judge wrong, labeller declined. Labeller: "d as the closest available metrics, not as an answer to the question. That is a decline, even though the figure 5 appears as a session count, since it is not presented as the median. VERDICT: declined"
- frozen baseline shipped_orders run 2 turn 1: judge wrong, labeller declined. Labeller: "ppear. The answer is a decline: it states the data does not cover the question. The proxy figure comes with an explicit caveat, so it is not a confident answer to the question asked. VERDICT: declined"
- hard custom-lightdash hard_turkish_vs_dutch_per_order run 1 turn 1: judge wrong, labeller declined. Labeller: "64. It explicitly says the data layer can't answer the country split. The overall figure is offered as context, not as the answer, and the response effectively declines the question. VERDICT: declined"

## What it means

- Five of the six disagreements are between two outcomes that are both not right (wrong against declined, or wrong against confident-wrong), so they leave accuracy unchanged; two of them would move the confident-wrong rate (Haiku read a stated scope as a hedge where Sonnet did not).
- One (`native-mcp`, `hard_mqls_social_september` run 1) moves accuracy: Haiku counted a figure the answer itself labelled a different metric as right; Sonnet read the answer as a decline.
- On this sample the judge's verdicts on accuracy are right in 59 of 60 turns, and the confident-wrong verdicts in all 16 sampled; it is the boundary between a hedged figure and a decline that the two models read differently.

## What stays unknown

- Sonnet is a second model, not ground truth: where they disagree, the owner's reading settles it.
- 60 turns bound the judge's error rate only loosely (54 of 60 agree; a 95% interval for the agreement is roughly 80% to 96%).

## Sources

- `judge.jsonl` (the `claude -p (haiku)` rows), `findings/429-judge-calibration/`, RULE.md § Scoring a run.
