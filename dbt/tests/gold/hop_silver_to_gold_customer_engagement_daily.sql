{{ config(tags=['gold', 'customer_actions']) }}

-- Per day, gold's funnel sessions equal silver's sessions with that step, and gold has a row for every
-- day silver has an action (a day row counts 1 on both sides).
{% set upstream %}
    select event_date as activity_date, 1 as day_rows,
           count(distinct case when action_type = 'page_view' then session_id end) as site_sessions,
           count(distinct case when action_type = 'add_to_cart' then session_id end) as cart_sessions,
           count(distinct case when action_type = 'checkout' then session_id end) as checkout_sessions
    from {{ ref('slv_customer_actions') }}
    group by event_date
{% endset %}

{% set downstream %}
    select activity_date, 1 as day_rows, site_sessions, cart_sessions, checkout_sessions
    from {{ ref('gld_customer_engagement_daily') }}
{% endset %}

{{ hop_mismatches('silver -> gold customer_engagement_daily', upstream, downstream, ['activity_date'],
                  ['day_rows', 'site_sessions', 'cart_sessions', 'checkout_sessions']) }}
