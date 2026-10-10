{{ config(alias='sales_by_country_daily', tags=['sales']) }}

-- Counts include cancelled orders; revenue excludes them, matching gold.
select
    o.order_date,
    c.country,
    count(*) as orders,
    coalesce(sum(case when o.status <> 'cancelled' then o.amount end), 0) as revenue_eur
from {{ ref('slv_orders') }} as o
inner join {{ ref('slv_customers') }} as c
    on c.customer_id = o.customer_id
group by o.order_date, c.country
