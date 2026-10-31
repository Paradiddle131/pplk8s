{{ config(alias='net_sales_daily', tags=['finance'], materialized='table') }}

-- Finance's daily revenue net of partner returns, one row per day with orders or returns.
-- Reads two pipelines' outputs (sales gold, returns silver); the finance_daily DAG waits for both
-- in ops.readiness before building it.
-- A return recorded on a day without orders gets its own row with revenue 0 (#150), so net revenue
-- over any period equals the net_revenue_eur metric and the returns hops stay strict.
-- A table, not a view (PLAN.md D20): dbt-postgres rebuilds a table by dropping the old one with
-- CASCADE, which would drop a view of another pipeline that reads it (issue #27).
with returns_daily as (
    select
        return_date,
        count(*) as returns_count,
        sum(amount) as returns_eur
    from {{ ref('slv_returns') }}
    group by return_date
),

days as (
    select order_date as day from {{ ref('gld_daily_sales') }}
    union distinct
    select return_date as day from returns_daily
)

select
    d.day as order_date,
    coalesce(s.revenue_eur, 0) as revenue_eur,
    coalesce(r.returns_count, 0) as returns_count,
    coalesce(r.returns_eur, 0) as returns_eur,
    coalesce(s.revenue_eur, 0) - coalesce(r.returns_eur, 0) as net_revenue_eur
from days as d
left join {{ ref('gld_daily_sales') }} as s
    on s.order_date = d.day
left join returns_daily as r
    on r.return_date = d.day
