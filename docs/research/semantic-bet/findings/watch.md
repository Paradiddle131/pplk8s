# The watch (#335)

One dated line per daily check of the sources in #335: no change, or what changed and its link.

- 2026-11-02: baseline taken in [the starting point](2026-11-02-324-starting-point.md).
- 2026-11-03 (`stated`, read 2026-11-03T01:56Z): two moves at Google, none at dbt.
  - Knowledge Catalog, 2026-11-02, Preview: [Knowledge Studio](https://docs.cloud.google.com/knowledge-catalog/docs/knowledge-studio) and [context sets](https://docs.cloud.google.com/knowledge-catalog/docs/context-sets), bounded bundles of table entries, "business concepts" (KPI formulas), verified parameterised "query templates" and documents that ground Gemini Enterprise and custom ADK agents through MCP or `lookupContext`; data agents and dbt or MetricFlow are not named, and metadata storage is billed once entries exist (a $0.00 question before any live use; for #326, #328).
  - BigQuery, 2026-11-02, GA: data agent monitoring (performance, adoption, latency and cost in Cloud Observability) ([release notes](https://docs.cloud.google.com/bigquery/docs/release-notes)); Conversational Analytics API: nothing since 2026-10-16 ([release notes](https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/release-notes)).
  - dbt: dbt-mcp 2.8.0 to 2.10.0 (2026-10-12 to 10-30) change nothing for metrics without the platform ([changelog](https://github.com/dbt-labs/dbt-mcp/blob/main/CHANGELOG.md)), so the 2.7.0 finding stands on paper; dbt-metricflow 0.15.0 (2026-09-10) and dbt-core 1.12.6 are still the latest on PyPI; Lightdash 3.128.0 (2026-11-02) is the version #334 measured.
  - Not read today: Apache Ossie.
