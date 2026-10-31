{{ config(tags=['gold', 'sales']) }}

-- Gold has one row per silver customer, and its orders and lifetime value add up to silver's orders:
-- an order whose customer is missing from silver would drop out of gold here.
{% set upstream %}
    select
        (select count(*) from {{ ref('slv_customers') }}) as customers,
        count(*) as orders,
        sum(case when status <> 'cancelled' then amount end) as lifetime_value_eur
    from {{ ref('slv_orders') }}
{% endset %}

{% set downstream %}
    select count(*) as customers, sum(orders) as orders, sum(lifetime_value_eur) as lifetime_value_eur
    from {{ ref('gld_customer_lifetime') }}
{% endset %}

{{ hop_mismatches('silver -> gold customer_lifetime', upstream, downstream,
                  [], ['customers', 'orders', 'lifetime_value_eur']) }}
