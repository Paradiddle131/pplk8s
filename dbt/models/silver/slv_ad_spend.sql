{{ config(alias='ad_spend', tags=['marketing']) }}

-- Latest row per spend_date, campaign_id: greatest _loaded_at, then greatest _run_id as tie-breaker.
with ranked as (
    select
        *,
        row_number() over (
            partition by spend_date, campaign_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_ad_spend') }}
)

select
    spend_date,
    campaign_id,
    impressions,
    clicks,
    spend,
    currency,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
