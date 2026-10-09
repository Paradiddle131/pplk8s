{{ config(alias='customer_lifetime') }}

-- One row per customer, including customers without orders (orders = 0, lifetime_value_eur = 0).
-- orders and the order dates count all orders; lifetime_value_eur excludes cancelled orders.
select
    c.customer_id,
    c.name,
    c.country,
    min(o.order_date) as first_order_date,
    max(o.order_date) as last_order_date,
    count(o.order_id) as orders,
    coalesce(sum(case when o.status <> 'cancelled' then o.amount end), 0) as lifetime_value_eur
from {{ ref('slv_customers') }} as c
left join {{ ref('slv_orders') }} as o
    on o.customer_id = c.customer_id
group by c.customer_id, c.name, c.country
