{{ config(alias='synthetic_partners', tags=['partner_outreach']) }}

select
    cast(partner_id as integer) as partner_id,
    cast(name as {{ dbt.type_string() }}) as name,
    cast(partner_type as {{ dbt.type_string() }}) as partner_type,
    cast(country as {{ dbt.type_string() }}) as country,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_partners') }}
