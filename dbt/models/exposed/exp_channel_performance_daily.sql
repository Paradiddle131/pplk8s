{{ config(alias='channel_performance_daily', tags=['marketing']) }}

-- Daily cost per lead and per booking for each channel, as a dashboard would compute them.
-- These are per-day ratios: averaging them over several days is not the period's cost per lead,
-- which is total spend over total leads (the metric cost_per_lead_eur, semantic/PLAN.md SL-8).
select
    activity_date,
    channel,
    ad_spend_eur,
    leads,
    bookings,
    ad_spend_eur / nullif(leads, 0) as cost_per_lead_eur,
    ad_spend_eur / nullif(bookings, 0) as cost_per_booking_eur
from {{ ref('gld_marketing_daily') }}
