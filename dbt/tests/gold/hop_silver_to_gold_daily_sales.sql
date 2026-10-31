{{ config(tags=['gold', 'sales']) }}

-- Per order_date, gold's counts and revenue equal silver's orders (cancelled count, revenue does not).
-- Lives in tests/gold/ and is tagged gold: it needs gold and silver built, so it runs with the gold stage only.
{% set upstream %}
    select
        order_date,
        count(*) as orders_total,
        count(case when status = 'cancelled' then 1 end) as orders_cancelled,
        sum(case when status <> 'cancelled' then amount end) as revenue_eur
    from {{ ref('slv_orders') }}
    group by order_date
{% endset %}

{% set downstream %}
    select order_date, orders_total, orders_cancelled, revenue_eur
    from {{ ref('gld_daily_sales') }}
{% endset %}

{{ hop_mismatches('silver -> gold daily_sales', upstream, downstream,
                  ['order_date'], ['orders_total', 'orders_cancelled', 'revenue_eur']) }}
