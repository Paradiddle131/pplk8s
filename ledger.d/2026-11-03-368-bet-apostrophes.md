## 2026-11-03 — Semantic track — the scorer reads typographic apostrophes as ASCII ones (#368)

- Done: `bet_rule.fold` turns ’ and ‘ into `'` before the decline, listed-hedge and hedge-like patterns match, a dated RULE.md line; every log scored on read again through `bet_eval.recode`.
- Evidence: one logged answer holds a typographic apostrophe (`custom-lightdash` `cost_per_lead_search` run 1, "I can’t isolate…"), now read as hedge-like; no turn moved and no judge request was needed (`docs/research/semantic-bet/findings/2026-11-03-367-scorer-wordings.md` § Typographic apostrophes); `make agent-test` and `make lint` pass.
- Open: curly quotes around a metric name keep `DECLINE`'s "no … metric" from matching; no logged outcome depends on it yet.
