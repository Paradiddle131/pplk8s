{{ config(alias='daily_sales') }}

-- Counts include cancelled orders; revenue excludes them.
-- customers_distinct counts customers with at least one non-cancelled order that day.
select
    order_date,
    count(*) as orders_total,
    count(case when status = 'cancelled' then 1 end) as orders_cancelled,
    coalesce(sum(case when status <> 'cancelled' then amount end), 0) as revenue_eur,
    count(distinct case when status <> 'cancelled' then customer_id end) as customers_distinct
from {{ ref('slv_orders') }}
group by order_date
