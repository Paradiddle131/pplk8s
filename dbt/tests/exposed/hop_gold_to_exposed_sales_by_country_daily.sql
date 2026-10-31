{{ config(tags=['exposed', 'sales']) }}

-- Per order_date, the countries add up to gold's day: an order whose customer is missing drops out here.
{% set upstream %}
    select order_date, orders_total as orders, revenue_eur
    from {{ ref('gld_daily_sales') }}
{% endset %}

{% set downstream %}
    select order_date, orders, revenue_eur
    from {{ ref('exp_sales_by_country_daily') }}
{% endset %}

{{ hop_mismatches('gold -> exposed sales_by_country_daily', upstream, downstream, ['order_date'],
                  ['orders', 'revenue_eur']) }}
