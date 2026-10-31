{{ config(tags=['exposed', 'sales']) }}

-- The weather join keeps every gold day once: no day is dropped or doubled.
{% set upstream %}
    select order_date, orders_total, orders_cancelled, revenue_eur, customers_distinct
    from {{ ref('gld_daily_sales') }}
{% endset %}

{% set downstream %}
    select order_date, orders_total, orders_cancelled, revenue_eur, customers_distinct
    from {{ ref('exp_daily_sales_with_weather') }}
{% endset %}

{{ hop_mismatches('gold -> exposed daily_sales_with_weather', upstream, downstream, ['order_date'],
                  ['orders_total', 'orders_cancelled', 'revenue_eur', 'customers_distinct']) }}
