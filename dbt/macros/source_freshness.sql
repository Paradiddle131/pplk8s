-- Source freshness into the warehouse (#130, semantic/PLAN.md SL-12): the on-run-end hook in
-- dbt_project.yml calls this after every command, and it acts only after `dbt source freshness`.
-- It replaces each checked source's row in ops.source_freshness with dbt's verdict, so the thresholds live
-- once, in models/sources.yml, and the warehouse's sql_exporter turns the rows into the SourceStale alert
-- (platform/compose/sql-exporter/source-freshness.collector.yml).
-- A table that could not be checked (missing, no permission) is `runtime error`, with no max_loaded_at.
-- Postgres and BigQuery alike: the types come from dbt's cross-database macros and type_timestamptz().

{% macro record_source_freshness(results) -%}
  {%- if not execute or flags.WHICH != "freshness" -%}{{ return("") }}{%- endif -%}
  {%- set rows = [] -%}
  {%- for result in results if result.node.resource_type == "source" -%}
    {%- set node = result.node -%}
    {%- set checked = result.snapshotted_at if result.snapshotted_at is defined else none -%}
    {%- set loaded = result.max_loaded_at if result.max_loaded_at is defined else none -%}
    {%- do rows.append("(" ~ [
        dbt.string_literal(node.source_name),
        dbt.string_literal(node.name),
        dbt.string_literal(result.status | string),
        _freshness_timestamp(loaded),
        _freshness_timestamp(checked) if checked is not none else "current_timestamp",
        _freshness_seconds(node.freshness.warn_after if node.freshness else none),
        _freshness_seconds(node.freshness.error_after if node.freshness else none),
        dbt.string_literal((result.message or "")[:500] | replace("'", "") | replace("\\", "")),
      ] | join(", ") ~ ")") -%}
  {%- endfor -%}
  {%- if rows | length == 0 -%}{{ return("") }}{%- endif -%}
  {%- set table = _source_freshness_relation() -%}
  {%- set keys = [] -%}
  {%- for result in results if result.node.resource_type == "source" -%}
    {%- do keys.append(dbt.string_literal(result.node.source_name ~ "." ~ result.node.name)) -%}
  {%- endfor -%}
  {{ return(
    _source_freshness_ddl() ~ ";\n"
    ~ "delete from " ~ table ~ " where " ~ dbt.concat(["source_name", "'.'", "table_name"]) ~ " in (" ~ keys | join(", ") ~ ");\n"
    ~ "insert into " ~ table
    ~ " (source_name, table_name, status, max_loaded_at, checked_at, warn_after_seconds, error_after_seconds, message) values\n  "
    ~ rows | join(",\n  ") ~ ";"
  ) }}
{%- endmacro %}

{# The table, created ahead of the first check by `dbt run-operation source_freshness_table` (`make services-up`
   runs it on the Compose warehouse), so the exporter's query never meets a missing table. #}
{% macro source_freshness_table() -%}
  {% do run_query(_source_freshness_ddl()) %}
{%- endmacro %}

{% macro _source_freshness_relation() -%}
  {{ return(api.Relation.create(database=target.database, schema="ops", identifier="source_freshness")) }}
{%- endmacro %}

{% macro _source_freshness_ddl() -%}
  {%- do adapter.create_schema(api.Relation.create(database=target.database, schema="ops")) -%}
  {{ return(
    "create table if not exists " ~ _source_freshness_relation() ~ " ("
    ~ "source_name " ~ dbt.type_string() ~ " not null, "
    ~ "table_name " ~ dbt.type_string() ~ " not null, "
    ~ "status " ~ dbt.type_string() ~ " not null, "
    ~ "max_loaded_at " ~ type_timestamptz() ~ ", "
    ~ "checked_at " ~ type_timestamptz() ~ " not null, "
    ~ "warn_after_seconds " ~ dbt.type_bigint() ~ ", "
    ~ "error_after_seconds " ~ dbt.type_bigint() ~ ", "
    ~ "message " ~ dbt.type_string() ~ ")"
  ) }}
{%- endmacro %}

{# A datetime dbt hands over (UTC), as a timestamp literal; null when the table could not be checked. #}
{% macro _freshness_timestamp(value) -%}
  {%- if value is none -%}null
  {%- else -%}cast({{ dbt.string_literal(value.strftime("%Y-%m-%d %H:%M:%S.%f") ~ "+00:00") }} as {{ type_timestamptz() }})
  {%- endif -%}
{%- endmacro %}

{# A threshold ({count, period}) in seconds; null when the source sets none. #}
{% macro _freshness_seconds(threshold) -%}
  {%- set per = {"minute": 60, "hour": 3600, "day": 86400} -%}
  {%- if threshold is none or threshold.count is none or threshold.period is none -%}null
  {%- else -%}{{ threshold.count * per[threshold.period | string] }}
  {%- endif -%}
{%- endmacro %}
