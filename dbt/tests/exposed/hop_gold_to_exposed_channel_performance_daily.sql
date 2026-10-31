{{ config(tags=['exposed', 'marketing']) }}

-- Per day and channel, the dashboard's spend, leads and bookings are gold's.
{% set upstream %}
    select activity_date, channel, ad_spend_eur, leads, bookings
    from {{ ref('gld_marketing_daily') }}
{% endset %}

{% set downstream %}
    select activity_date, channel, ad_spend_eur, leads, bookings
    from {{ ref('exp_channel_performance_daily') }}
{% endset %}

{{ hop_mismatches('gold -> exposed channel_performance_daily', upstream, downstream, ['activity_date', 'channel'],
                  ['ad_spend_eur', 'leads', 'bookings']) }}
