{{ config(alias='marketing_daily', tags=['marketing']) }}

-- One row per (activity_date, channel) with any spend, lead or booking: the hand-written daily
-- marketing aggregate, kept as the parity oracle for the marketing metrics (semantic/PLAN.md SL-8).
-- Leads count on the day they were created, bookings on the day they were made, both under the
-- channel of the campaign they came from.
with spend as (
    select s.spend_date as activity_date, c.channel,
           sum(s.spend) as ad_spend_eur, sum(s.clicks) as ad_clicks, sum(s.impressions) as ad_impressions
    from {{ ref('slv_ad_spend') }} as s
    inner join {{ ref('slv_campaigns') }} as c on c.campaign_id = s.campaign_id
    group by s.spend_date, c.channel
),

leads as (
    select l.created_date as activity_date, c.channel, count(*) as leads
    from {{ ref('slv_leads') }} as l
    inner join {{ ref('slv_campaigns') }} as c on c.campaign_id = l.campaign_id
    group by l.created_date, c.channel
),

bookings as (
    select b.booked_date as activity_date, c.channel, count(*) as bookings, sum(b.amount) as booking_value_eur
    from {{ ref('slv_bookings') }} as b
    inner join {{ ref('slv_campaigns') }} as c on c.campaign_id = b.campaign_id
    group by b.booked_date, c.channel
),

days as (
    select activity_date, channel from spend
    union distinct
    select activity_date, channel from leads
    union distinct
    select activity_date, channel from bookings
)

select
    d.activity_date,
    d.channel,
    coalesce(s.ad_spend_eur, 0) as ad_spend_eur,
    coalesce(s.ad_clicks, 0) as ad_clicks,
    coalesce(s.ad_impressions, 0) as ad_impressions,
    coalesce(l.leads, 0) as leads,
    coalesce(b.bookings, 0) as bookings,
    coalesce(b.booking_value_eur, 0) as booking_value_eur
from days as d
left join spend as s on s.activity_date = d.activity_date and s.channel = d.channel
left join leads as l on l.activity_date = d.activity_date and l.channel = d.channel
left join bookings as b on b.activity_date = d.activity_date and b.channel = d.channel
