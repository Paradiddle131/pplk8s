{{ config(tags=['governed'], enabled=target.type == 'bigquery') }}

-- The governed tables (semantic/PLAN.md SL-24) are MetricFlow's numbers; the hand-written gold and exposed
-- tables are the parity oracle, as for every metric (SL-9). Per day: the daily tables' additive columns summed
-- over their dimensions, and the by-period table's day totals, equal finance's net sales and gold's daily sales.
-- A day with returns but no orders has its own row on both sides (SL-9, #150). BigQuery only, like the tables.
{% set upstream %}
    select
        g.order_date,
        g.orders_total,
        g.orders_cancelled,
        g.revenue_eur,
        g.customers_distinct,
        e.returns_count,
        e.returns_eur,
        e.net_revenue_eur
    from {{ ref('exp_net_sales_daily') }} as e
    left join {{ ref('gld_daily_sales') }} as g on g.order_date = e.order_date
{% endset %}

{% set downstream %}
    with orders as (
        select
            metric_time__day as order_date,
            sum(orders_total) as orders_total,
            sum(orders_cancelled) as orders_cancelled,
            sum(revenue_eur) as revenue_eur,
            sum(net_revenue_eur) as net_revenue_eur
        from {{ ref('gov_orders_daily') }}
        group by metric_time__day
    ),

    returns as (
        select
            metric_time__day as order_date,
            sum(returns_count) as returns_count,
            sum(returns_eur) as returns_eur
        from {{ ref('gov_returns_daily') }}
        group by metric_time__day
    ),

    distinct_customers as (
        select period_start as order_date, customers_distinct
        from {{ ref('gov_orders_by_period') }}
        where grain = 'day' and slice = 'total'
    )

    select
        days.order_date,
        o.orders_total,
        o.orders_cancelled,
        o.revenue_eur,
        c.customers_distinct,
        r.returns_count,
        r.returns_eur,
        o.net_revenue_eur
    from (
        select order_date from orders
        union distinct
        select order_date from returns
    ) as days
    left join orders as o on o.order_date = days.order_date
    left join returns as r on r.order_date = days.order_date
    left join distinct_customers as c on c.order_date = days.order_date
{% endset %}

{{ hop_mismatches(
    'governed -> gold daily_sales and exposed net_sales_daily',
    upstream,
    downstream,
    ['order_date'],
    ['orders_total', 'orders_cancelled', 'revenue_eur', 'customers_distinct', 'returns_count', 'returns_eur', 'net_revenue_eur'],
    tolerance=0.005
) }}
