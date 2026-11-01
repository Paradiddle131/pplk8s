## 2026-11-02 — Semantic — follow-ups, "how was this computed?" and ambiguous terms in the eval

- Done: eval cases can be conversations whose turns share one ADK session; seven new cases (four follow-ups that add a breakdown, change the period, switch the metric or ask how a figure was computed, one more definition, two ambiguous terms), 56 cases in all.
- Done: two custom ADK metrics, `definition_quoted` and `term_disambiguated`; each metric scores only the turns it applies to.
- Done: glossary terms `Customers` and `Sales` say they are ambiguous on their own; the semantic agent asks which meaning instead of picking one, carries a follow-up's context and quotes a metric's description when asked how a figure was computed. `DBT_IMAGE` 0.7.41, `AGENT_IMAGE` 0.1.38.
- Evidence: see the PR.
- Decisions: `semantic/PLAN.md` SL-5 amended (five metrics, conversations, ambiguity in the glossary).
- Open: none.
