{{ config(tags=['exposed', 'finance']) }}

-- Per order_date, finance's revenue is gold's.
{% set upstream %}
    select order_date, revenue_eur
    from {{ ref('gld_daily_sales') }}
{% endset %}

{% set downstream %}
    select order_date, revenue_eur
    from {{ ref('exp_net_sales_daily') }}
{% endset %}

{{ hop_mismatches('gold -> exposed net_sales_daily', upstream, downstream, ['order_date'], ['revenue_eur']) }}
