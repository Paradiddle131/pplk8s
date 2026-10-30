{{ config(alias='synthetic_ad_spend', tags=['marketing']) }}

select
    cast(spend_date as date) as spend_date,
    cast(campaign_id as integer) as campaign_id,
    cast(impressions as integer) as impressions,
    cast(clicks as integer) as clicks,
    cast(spend as numeric(12,2)) as spend,
    cast(currency as {{ dbt.type_string() }}) as currency,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_ad_spend') }}
