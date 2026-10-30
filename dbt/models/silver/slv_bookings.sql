{{ config(alias='bookings', tags=['marketing']) }}

-- Latest row per booking_id: greatest _loaded_at, then greatest _run_id as tie-breaker.
-- campaign_id comes from the booking's lead, so bookings group by campaign like spend and leads.
with ranked as (
    select
        *,
        row_number() over (
            partition by booking_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_bookings') }}
)

select
    b.booking_id,
    b.lead_id,
    l.campaign_id,
    b.booked_ts,
    {{ utc_date('b.booked_ts') }} as booked_date,
    b.amount,
    b.currency,
    b._run_id,
    b._loaded_at
from ranked as b
left join {{ ref('slv_leads') }} as l
    on l.lead_id = b.lead_id
where b.row_rank = 1
