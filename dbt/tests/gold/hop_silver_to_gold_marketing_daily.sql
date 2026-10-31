{{ config(tags=['gold', 'marketing']) }}

-- Per day, gold's spend, leads and bookings over all channels equal silver's, each on its own date:
-- spend on spend_date, leads on created_date, bookings on booked_date.
{% set upstream %}
    select spend_date as activity_date, sum(spend) as ad_spend_eur, sum(clicks) as ad_clicks,
           sum(impressions) as ad_impressions, 0 as leads, 0 as bookings, 0 as booking_value_eur
    from {{ ref('slv_ad_spend') }}
    group by spend_date
    union all
    select created_date, 0, 0, 0, count(*), 0, 0
    from {{ ref('slv_leads') }}
    group by created_date
    union all
    select booked_date, 0, 0, 0, 0, count(*), sum(amount)
    from {{ ref('slv_bookings') }}
    group by booked_date
{% endset %}

{% set downstream %}
    select activity_date, ad_spend_eur, ad_clicks, ad_impressions, leads, bookings, booking_value_eur
    from {{ ref('gld_marketing_daily') }}
{% endset %}

{{ hop_mismatches('silver -> gold marketing_daily', upstream, downstream, ['activity_date'],
                  ['ad_spend_eur', 'ad_clicks', 'ad_impressions', 'leads', 'bookings', 'booking_value_eur']) }}
