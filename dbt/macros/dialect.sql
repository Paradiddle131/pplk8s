-- Dialect seams (semantic/PLAN.md R7): one macro per construct Postgres and BigQuery spell
-- differently, through dbt's adapter.dispatch, so the models compile on either target unchanged.
-- `default__` is the lab's Postgres; `bigquery__` is what the compile-only BigQuery target emits.

-- The UTC calendar day of a timestamptz / TIMESTAMP column.
{% macro utc_date(column) -%}
    {{ return(adapter.dispatch('utc_date')(column)) }}
{%- endmacro %}

{% macro default__utc_date(column) -%}
    cast({{ column }} at time zone 'UTC' as date)
{%- endmacro %}

{% macro bigquery__utc_date(column) -%}
    date({{ column }}, 'UTC')
{%- endmacro %}

-- One row per calendar day from start to end inclusive, as `date_day`; start and end are
-- 'YYYY-MM-DD' strings. dbt.date_spine counts its days with a warehouse query, so it cannot
-- compile offline; these need none.
{% macro day_spine(start, end) -%}
    {{ return(adapter.dispatch('day_spine')(start, end)) }}
{%- endmacro %}

{% macro default__day_spine(start, end) -%}
    select cast(d as date) as date_day
    from generate_series(date '{{ start }}', date '{{ end }}', interval '1 day') as d
{%- endmacro %}

{% macro bigquery__day_spine(start, end) -%}
    select date_day
    from unnest(generate_date_array(date '{{ start }}', date '{{ end }}')) as date_day
{%- endmacro %}

-- A time-zone-aware timestamp type: Postgres timestamptz, BigQuery TIMESTAMP (always UTC).
-- dbt.type_timestamp() is the zoneless one on Postgres, so it does not fit.
{% macro type_timestamptz() -%}
    {{ return(adapter.dispatch('type_timestamptz')()) }}
{%- endmacro %}

{% macro default__type_timestamptz() -%}
    timestamptz
{%- endmacro %}

{% macro bigquery__type_timestamptz() -%}
    timestamp
{%- endmacro %}
