{{ config(alias='net_sales_daily', tags=['finance']) }}

-- Finance view: daily revenue net of partner returns, one row per order_date of gold.daily_sales.
-- Reads two pipelines' outputs (sales gold, returns silver); the finance_daily DAG waits for both
-- in ops.readiness before building it.
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
