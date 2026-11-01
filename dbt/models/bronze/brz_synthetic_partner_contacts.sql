{{ config(alias='synthetic_partner_contacts', tags=['partner_outreach']) }}

select
    cast(contact_id as {{ dbt.type_string() }}) as contact_id,
    cast(partner_id as integer) as partner_id,
    cast(contact_name as {{ dbt.type_string() }}) as contact_name,
    cast(email as {{ dbt.type_string() }}) as email,
    cast(phone as {{ dbt.type_string() }}) as phone,
    cast(preferred_channel as {{ dbt.type_string() }}) as preferred_channel,
    cast(consent as {{ dbt.type_boolean() }}) as consent,
    cast(opted_out_ts as {{ type_timestamptz() }}) as opted_out_ts,
    cast(updated_ts as {{ type_timestamptz() }}) as updated_ts,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_partner_contacts') }}
