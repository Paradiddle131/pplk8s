## 2026-11-04 — Semantic track — the free model's day: the judge's backlog and `custom-metricflow` on both sets

- Done: the blind judge on every waiting turn of both sets (98 verdicts); `custom-metricflow` on the free model finished run 1 of the frozen set and all three runs of the hard set, plus 14 cases of the frozen set's run 2; `eval.md` regenerated after each pass.
- Evidence: 830 logged free requests (the key's free count 831 of 1,000 at 01:28Z); the rule on both sets for the deciding pair reads "not worth building" (frozen: accuracy -0.083 [-0.149, -0.017] against `native-context-bare`; hard: -0.182 [-0.295, -0.089] against `native-context`) (`docs/research/semantic-bet/findings/2026-11-04-free-model-passes.md`).
- Open: three turns wait for the judge, whose model failed upstream from 01:14Z; the frozen set's runs 2 and 3 of `custom-metricflow` on the free model.
