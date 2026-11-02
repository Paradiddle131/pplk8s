## 2026-11-02 — Semantic — follow-ups, "how was this computed?" and ambiguous terms in the eval

- Done: eval cases can be conversations whose turns share one ADK session; seven new cases (four follow-ups that add a breakdown, change the period, switch the metric or ask how a figure was computed, one more definition, two ambiguous terms), 56 cases in all.
- Done: two custom ADK metrics, `definition_quoted` and `term_disambiguated`; each metric scores only the turns it applies to.
- Done: glossary terms `Customers` and `Sales` say they are ambiguous on their own; the semantic agent asks which meaning instead of picking one, carries a follow-up's context and quotes a metric's description when asked how a figure was computed. `DBT_IMAGE` 0.7.41, `AGENT_IMAGE` 0.1.38.
- Evidence: live `make agent-eval` (free model, 56 cases): semantic agent 56 of 56, conversations 7 of 7; text-to-SQL baseline 36 of 56, conversations 4 of 7 (it quoted no definition and picked one reading of "customers"). `make check` exit 0, `make catalog-check` (14 glossary terms), `make verify`, `make agent-deploy-check` green on cloud; `make gcp-image-check` passed on cloud in a later wake (dbt build PASS=173, the 31 hops, MetricFlow 2 days) once it loads the fixture into `dbt_dev` itself: in a fresh session it failed on `database "dbt_dev" does not exist`.
- Decisions: `semantic/PLAN.md` SL-5 amended (five metrics, conversations, ambiguity in the glossary).
- Open: none.
