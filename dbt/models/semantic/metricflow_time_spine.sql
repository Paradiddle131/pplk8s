{{ config(alias='time_spine', tags=['sales']) }}

-- MetricFlow's daily time spine (semantic/PLAN.md SL-1): one row per calendar day, joined when a
-- metric is queried by metric_time. Owned by the sales pipeline, like the orders it dates.
-- dialect: generate_series is Postgres; BigQuery uses unnest(generate_date_array(...)).
select cast(d as date) as date_day
from generate_series(date '2024-01-01', date '2027-12-31', interval '1 day') as d
