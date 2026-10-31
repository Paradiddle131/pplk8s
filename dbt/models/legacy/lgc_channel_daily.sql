{{ config(alias='channel_daily') }}

-- The marketing budget automation's table as a scheduled query wrote it before the layers: spend,
-- leads and bookings per day and channel straight off silver, and the day's cost per lead and per
-- booking. Its new model is exposed.channel_performance_daily (semantic/PLAN.md SL-11).
with activity as (
    select s.spend_date as day, c.channel, s.spend, 0 as leads, 0 as bookings
    from {{ ref('slv_ad_spend') }} as s
    inner join {{ ref('slv_campaigns') }} as c on c.campaign_id = s.campaign_id
    union all
    select l.created_date, c.channel, 0, 1, 0
    from {{ ref('slv_leads') }} as l
    inner join {{ ref('slv_campaigns') }} as c on c.campaign_id = l.campaign_id
    union all
    select b.booked_date, coalesce(c.channel, 'unknown'), 0, 0, 1
    from {{ ref('slv_bookings') }} as b
    left join {{ ref('slv_campaigns') }} as c on c.campaign_id = b.campaign_id
)

select
    day,
    channel,
    sum(spend) as spend,
    sum(leads) as leads,
    sum(bookings) as bookings,
    sum(spend) / nullif(sum(leads), 0) as cost_per_lead,
    sum(spend) / nullif(sum(bookings), 0) as cost_per_booking
from activity
group by day, channel
