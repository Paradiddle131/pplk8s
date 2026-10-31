{{ config(alias='daily_net_sales') }}

-- The finance dashboard's table as a scheduled query wrote it before the layers: one statement off
-- the cleaned orders and returns, with the dashboard's own column names. Its new model is
-- exposed.net_sales_daily; the parity report compares the two (semantic/PLAN.md SL-11).
select
    o.order_date as sales_date,
    sum(case when o.status <> 'cancelled' then o.amount else 0 end) as gross_revenue,
    coalesce(max(r.returns_amount), 0) as returns_amount,
    sum(case when o.status <> 'cancelled' then o.amount else 0 end) - coalesce(max(r.returns_amount), 0) as net_revenue
from {{ ref('slv_orders') }} as o
left join (
    select return_date, sum(amount) as returns_amount
    from {{ ref('slv_returns') }}
    group by return_date
) as r
    on r.return_date = o.order_date
group by o.order_date
