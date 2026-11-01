{{ config(alias='synthetic_outreach_messages', tags=['partner_outreach']) }}

select
    cast(message_id as {{ dbt.type_string() }}) as message_id,
    cast(contact_id as {{ dbt.type_string() }}) as contact_id,
    cast(channel as {{ dbt.type_string() }}) as channel,
    cast(sent_ts as {{ type_timestamptz() }}) as sent_ts,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_outreach_messages') }}
