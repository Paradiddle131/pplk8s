{{ config(alias='synthetic_campaigns', tags=['marketing']) }}

select
    cast(campaign_id as integer) as campaign_id,
    cast(name as {{ dbt.type_string() }}) as name,
    cast(channel as {{ dbt.type_string() }}) as channel,
    cast(market as {{ dbt.type_string() }}) as market,
    cast(start_date as date) as start_date,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_campaigns') }}
