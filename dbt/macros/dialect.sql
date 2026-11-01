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

-- The first day of the fiscal period (quarter or year) holding a date, for a fiscal year that starts on the
-- first day of month `start_month` (2: February): shift back to the calendar, truncate, shift forward.
{% macro fiscal_period_start(column, grain, start_month) -%}
    {{ return(adapter.dispatch('fiscal_period_start')(column, grain, start_month)) }}
{%- endmacro %}

{% macro default__fiscal_period_start(column, grain, start_month) -%}
    cast(date_trunc('{{ grain }}', {{ column }} - interval '{{ start_month - 1 }} month')
         + interval '{{ start_month - 1 }} month' as date)
{%- endmacro %}

{% macro bigquery__fiscal_period_start(column, grain, start_month) -%}
    date_add(date_trunc(date_sub({{ column }}, interval {{ start_month - 1 }} month), {{ grain }}),
             interval {{ start_month - 1 }} month)
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

-- A timestamptz / TIMESTAMP expression moved back by a number of hours. dbt.dateadd casts to the
-- zoneless DATETIME on BigQuery, which a TIMESTAMP column does not compare with.
{% macro hours_before(expression, hours) -%}
    {{ return(adapter.dispatch('hours_before')(expression, hours)) }}
{%- endmacro %}

{% macro default__hours_before(expression, hours) -%}
    ({{ expression }} - interval '{{ hours }} hours')
{%- endmacro %}

{% macro bigquery__hours_before(expression, hours) -%}
    timestamp_sub({{ expression }}, interval {{ hours }} hour)
{%- endmacro %}

-- A DATE expression moved back by a number of days, still a DATE (dbt.dateadd returns a timestamp).
{% macro days_before(expression, days) -%}
    {{ return(adapter.dispatch('days_before')(expression, days)) }}
{%- endmacro %}

{% macro default__days_before(expression, days) -%}
    ({{ expression }} - {{ days }})
{%- endmacro %}

{% macro bigquery__days_before(expression, days) -%}
    date_sub({{ expression }}, interval {{ days }} day)
{%- endmacro %}

-- The days from one timestamptz / TIMESTAMP to a later one, as a numeric rounded to 4 places.
{% macro days_between(start, end) -%}
    {{ return(adapter.dispatch('days_between')(start, end)) }}
{%- endmacro %}

{% macro default__days_between(start, end) -%}
    round(cast(extract(epoch from ({{ end }} - {{ start }})) / 86400 as numeric), 4)
{%- endmacro %}

{% macro bigquery__days_between(start, end) -%}
    round(cast(timestamp_diff({{ end }}, {{ start }}, second) / 86400 as numeric), 4)
{%- endmacro %}

-- The Monday that starts a date's ISO week, as a date: Postgres' date_trunc('week') is ISO,
-- BigQuery's WEEK starts on Sunday, so it truncates to ISOWEEK.
{% macro iso_week_start(column) -%}
    {{ return(adapter.dispatch('iso_week_start')(column)) }}
{%- endmacro %}

{% macro default__iso_week_start(column) -%}
    cast(date_trunc('week', {{ column }}) as date)
{%- endmacro %}

{% macro bigquery__iso_week_start(column) -%}
    date_trunc({{ column }}, isoweek)
{%- endmacro %}
