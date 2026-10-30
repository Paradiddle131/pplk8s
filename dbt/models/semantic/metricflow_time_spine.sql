{{ config(alias='time_spine', tags=['sales']) }}

-- MetricFlow's daily time spine (semantic/PLAN.md SL-1): one row per calendar day, joined when a
-- metric is queried by metric_time. Owned by the sales pipeline, like the orders it dates.
{{ day_spine('2024-01-01', '2027-12-31') }}
