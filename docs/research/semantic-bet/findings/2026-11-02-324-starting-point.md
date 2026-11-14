# The starting point: desk research, grilling and review (2026-11-02)

What one session established before any measurement: three research agents, three grilling rounds and a cold review.
Every fact here is `stated` (read in the source on 2026-11-02) unless it says `measured`; the track's issues measure what matters.

## The premise, corrected

- Outside Looker, no GCP agent is **bound** to a dbt semantic layer's definitions; GCP can only **shape** what an agent reads (governed views or table functions, verified queries, routines, graph measures) or **ground** it (Knowledge Catalog).
- With a Looker Explore as source, a data agent picks fields and filters and Looker writes the SQL: the only bound path; Looker is out of scope (owner, 2026-11-02).
- Whether shaping or grounding is enough is empirical, per warehouse: that is this track's question.

## Google, as read on 2026-11-02

- Knowledge Catalog (Dataplex renamed) imports dbt artifacts with `gcloud dataplex dbt metadata-jobs create`, MetricFlow semantic models, metrics and saved queries included (`dbt-semantic-model`, `dbt-metric`, `dbt-saved-query`): GA 2026-09-24 ([dbt import](https://docs.cloud.google.com/knowledge-catalog/docs/dbt-transfer), [release notes](https://docs.cloud.google.com/knowledge-catalog/docs/release-notes)).
- Google's post of 2026-10-29 says the catalog grounds "Gemini agent, BigQuery Conversational Analytics, and your custom agents" in the metrics and claims "nearly 4X more accurate" from internal benchmarks, with no method ([post](https://cloud.google.com/blog/products/data-analytics/expanded-semantic-model-support-in-knowledge-catalog)); no doc says a data agent reads an imported metric's formula.
- Catalog metadata storage costs $2 per GiB-month past about 1 MiB free (search summaries of [pricing](https://cloud.google.com/dataplex/pricing); confirm on the page).
- Data agents (Conversational Analytics API): GA for BigQuery since 2026-06-23; graphs GA 2026-10-01; tables and graphs in one agent GA 2026-09-30; publishing to Gemini Enterprise GA 2026-10-14; conversation logging GA 2026-10-26 ([release notes](https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/release-notes)).
- Agents "can also take advantage of measures defined on your graph"; verified queries are optional ("Deterministic SQL that executes when it matches"); UDFs are knowledge sources; no setting restricts an agent to verified queries, routines or measures ([overview](https://docs.cloud.google.com/bigquery/docs/conversational-analytics)).
- `userFunctions.bqRoutines` is "a list of BigQuery routines", each described "to tell the agent when to use the UDF": table functions are not documented (#323).
- Pricing: $3 per million input and $20 per million output data tokens, free trial "through December 31, 2026" ([pricing](https://cloud.google.com/products/data-agents/pricing)).
- Conversation logging skips turns on sources with row policies, column security or masking, never logs generated SQL, and "doesn't look through views" ([logging](https://docs.cloud.google.com/bigquery/docs/conversation-logging-overview)).
- Model Armor has no documented integration with data agents ([integrations](https://docs.cloud.google.com/model-armor/integrations)).
- BigQuery Graph GA 2026-08-31; measures Preview since 2026-04-22 (a GA post dated 2026-10-28 answered 404); measures support SUM, AVG, COUNT, MIN, MAX on one element table, GQL can't reference them, `GRAPH_EXPAND` runs on demand, GQL needs an Enterprise reservation, core graph processing goes Enterprise-only on 2027-04-26 ([measures](https://docs.cloud.google.com/bigquery/docs/graph-measures), [release notes](https://docs.cloud.google.com/bigquery/docs/release-notes)).
- Row policies apply through logical and materialised views; table functions and authorized routines are not documented ([row-level security with other features](https://docs.cloud.google.com/bigquery/docs/using-row-level-security-with-features)).
- BigQuery's remote MCP server is GA (2026-04-20): `execute_sql_readonly` and metadata tools, OAuth, `roles/mcp.toolUser`, no semantic tool ([BigQuery MCP](https://docs.cloud.google.com/bigquery/docs/use-bigquery-mcp)); Knowledge Catalog serves `lookup_context` over MCP ([reference](https://docs.cloud.google.com/dataplex/docs/reference/mcp)).
- MCP Toolbox for Databases forwards a caller's token to BigQuery with `useClientOAuth` ([source](https://mcp-toolbox.dev/integrations/bigquery/source/)).
- Apache Ossie (formerly Open Semantic Interchange) is incubating; Google is "in the process of joining"; dbt 1.12 reads Ossie.

## The landscape

- Semantic engines are commodity: MetricFlow (Apache-2.0 since Oct 2025), Cube Core, Malloy, Boring Semantic Layer.
- Per-user metric queries exist in Looker, Lightdash (Enterprise, for its AI agents) and dbt's paid Semantic Layer (personal tokens); nothing free on dbt Core.
- dbt-mcp's semantic-layer tools need the dbt platform; dbt's exports (views from saved queries) are paid.
- GenBI apps are crowded (Wren AI, Lightdash, Metabase, Superset); Vanna was archived 2026-03-29.
- Snowflake (semantic views, Cortex Analyst) and Databricks (metric views, Genie) bundle semantics, identity and the agent in the platform.
- Vendor benchmarks agree that coverage dominates: dbt's (2026-04-07) went from 64.5% to 72.7% on all questions while covered ones reached 100%.

## The lab, measured before this track

- `measured`: the semantic agent 59 of 59 against the text-to-SQL baseline's 40 of 59 (`docs/research/semantic-agent-eval.md`, 2026-11-02), on one free model, single runs, with 47 of 49 single questions covered by a metric and a baseline that reads only gold and exposed.
- `measured`: PR #310's data agent answered "total revenue over 1 and 2 October 2026" right (€1,850.34) and wrote its own SQL over `silver.orders`; its eval arms are scored by a separate run.
- pplk8s's 57 metrics: 33 simple, 10 ratio, 4 derived, 6 cumulative, 4 conversion, plus offsets, a median and a non-additive one; most trap-prone ones won't compile to graph measures.

## What the grilling and the review settled

- Don't build a platform; the eval is the asset that transfers in every case.
- Governed objects are views or table functions, never aggregate tables over row-scoped sources; views over row-scoped sources may switch conversation logging back on (to measure, #332).
- If anything is served, its first form is generated MCP Toolbox tools over the table functions, with MetricFlow at build time only (#330).
- The eval's rule is fixed before any run: paired differences with a bootstrap interval, trap accuracy, all-question accuracy and a confident-wrong rate (#325).
- For transfer to work, the riskiest assumption was "work runs MetricFlow": the owner confirmed it does (2026-11-02).

## The lab project's credential, checked with `testIamPermissions` (2026-11-02)

- Held: BigQuery datasets, tables, routines and jobs; data agents create, chat, get and list; Knowledge Catalog entries and entry groups get; `logging.logEntries.list`.
- Not held: `bigquery.rowAccessPolicies.create` at project level, any `dataplex` write, any Cloud Storage write, `mcp.tools.call`, data agents update and delete.
- The $0 guard refuses every `gcloud dataplex` write verb, `--help` included.
