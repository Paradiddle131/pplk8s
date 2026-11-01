{{ config(alias='synthetic_outreach_replies', tags=['partner_outreach']) }}

select
    cast(reply_id as {{ dbt.type_string() }}) as reply_id,
    cast(message_id as {{ dbt.type_string() }}) as message_id,
    cast(replied_ts as {{ type_timestamptz() }}) as replied_ts,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_outreach_replies') }}
