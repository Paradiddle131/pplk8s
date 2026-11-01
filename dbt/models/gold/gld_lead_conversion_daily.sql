{{ config(alias='lead_conversion_daily', tags=['marketing']) }}

-- One row per day a lead was created: the leads of that day and those that booked within 30 days,
-- hand-written as the parity oracle for the conversion metric lead_to_booking_rate (semantic/PLAN.md
-- SL-9). A lead converts when its booking's day is on or after the lead's creation day and fewer than
-- 30 days after it, and counts on the lead's creation day; a lead books at most once (silver's test).
with leads as (
    select lead_id, created_date from {{ ref('slv_leads') }}
),

bookings as (
    select lead_id, booked_date from {{ ref('slv_bookings') }}
),

daily as (
    select
        l.created_date,
        count(*) as leads,
        count(b.lead_id) as booked_leads
    from leads as l
    left join bookings as b
        on b.lead_id = l.lead_id
        and l.created_date <= b.booked_date
        and l.created_date > {{ days_before('b.booked_date', 30) }}
    group by l.created_date
)

select
    created_date,
    leads,
    booked_leads,
    cast(booked_leads as {{ dbt.type_numeric() }}) / leads as lead_to_booking_rate
from daily
