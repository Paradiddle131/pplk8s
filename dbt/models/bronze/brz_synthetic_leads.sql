{{ config(alias='synthetic_leads', tags=['marketing']) }}

select
    cast(lead_id as {{ dbt.type_string() }}) as lead_id,
    cast(campaign_id as integer) as campaign_id,
    cast(created_ts as {{ type_timestamptz() }}) as created_ts,
    cast(country as {{ dbt.type_string() }}) as country,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_leads') }}
