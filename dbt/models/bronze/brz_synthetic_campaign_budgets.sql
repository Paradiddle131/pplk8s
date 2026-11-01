{{ config(alias='synthetic_campaign_budgets', tags=['marketing']) }}

select
    cast(snapshot_date as date) as snapshot_date,
    cast(campaign_id as integer) as campaign_id,
    cast(budget_eur as numeric(12,2)) as budget_eur,
    cast(remaining_eur as numeric(12,2)) as remaining_eur,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_campaign_budgets') }}
