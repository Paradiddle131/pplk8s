{{ config(alias='net_sales_daily', tags=['finance'], materialized='table') }}

-- Finance's daily revenue net of partner returns, one row per order_date of gold.daily_sales.
-- Reads two pipelines' outputs (sales gold, returns silver); the finance_daily DAG waits for both
-- in ops.readiness before building it.
-- A table, not a view (PLAN.md D20): dbt-postgres rebuilds a table by dropping the old one with
-- CASCADE, which would drop a view of another pipeline that reads it (issue #27).
with returns_daily as (
    select
        return_date,
        count(*) as returns_count,
        sum(amount) as returns_eur
    from {{ ref('slv_returns') }}
    group by return_date
)

select
    s.order_date,
    s.revenue_eur,
    coalesce(r.returns_count, 0) as returns_count,
    coalesce(r.returns_eur, 0) as returns_eur,
    s.revenue_eur - coalesce(r.returns_eur, 0) as net_revenue_eur
from {{ ref('gld_daily_sales') }} as s
left join returns_daily as r
    on r.return_date = s.order_date
