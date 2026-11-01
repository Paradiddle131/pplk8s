{{ config(alias='synthetic_customer_actions', tags=['customer_actions']) }}

select
    cast(event_id as {{ dbt.type_string() }}) as event_id,
    cast(customer_id as integer) as customer_id,
    cast(session_id as {{ dbt.type_string() }}) as session_id,
    cast(action_type as {{ dbt.type_string() }}) as action_type,
    cast(channel as {{ dbt.type_string() }}) as channel,
    cast(event_ts as {{ type_timestamptz() }}) as event_ts,
    cast(received_ts as {{ type_timestamptz() }}) as received_ts,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_customer_actions') }}
