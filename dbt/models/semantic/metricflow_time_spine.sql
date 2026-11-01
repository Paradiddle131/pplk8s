{{ config(alias='time_spine', tags=['sales']) }}

-- MetricFlow's daily time spine (semantic/PLAN.md SL-1): one row per calendar day, joined when a
-- metric is queried by metric_time. Owned by the sales pipeline, like the orders it dates.
-- The fiscal calendar rides on it as custom granularities (semantic.yml): the fiscal year starts on
-- 1 February (var fiscal_year_start_month), and each period is named by its first day.
select
    date_day,
    {{ fiscal_period_start('date_day', 'quarter', var('fiscal_year_start_month')) }} as fiscal_quarter,
    {{ fiscal_period_start('date_day', 'year', var('fiscal_year_start_month')) }} as fiscal_year
from ({{ day_spine('2024-01-01', '2027-12-31') }}) as days
