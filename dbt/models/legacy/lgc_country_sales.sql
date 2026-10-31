{{ config(alias='country_sales') }}

-- The sales agent's table as a scheduled query wrote it before the layers. Its revenue is the one
-- calculated field computed differently: it sums every order, cancelled ones included, where the
-- metric revenue_eur and exposed.sales_by_country_daily leave cancelled orders out. The parity
-- report shows the difference; the rehearsal keeps it, so the agent's switch waits on it.
select
    o.order_date as sales_date,
    c.country,
    count(*) as orders,
    sum(o.amount) as revenue
from {{ ref('slv_orders') }} as o
inner join {{ ref('slv_customers') }} as c
    on c.customer_id = o.customer_id
group by o.order_date, c.country
