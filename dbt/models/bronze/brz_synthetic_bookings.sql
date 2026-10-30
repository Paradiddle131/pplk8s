{{ config(alias='synthetic_bookings', tags=['marketing']) }}

select
    cast(booking_id as {{ dbt.type_string() }}) as booking_id,
    cast(lead_id as {{ dbt.type_string() }}) as lead_id,
    cast(booked_ts as {{ type_timestamptz() }}) as booked_ts,
    cast(amount as numeric(12,2)) as amount,
    cast(currency as {{ dbt.type_string() }}) as currency,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_bookings') }}
