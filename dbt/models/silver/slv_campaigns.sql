{{ config(alias='campaigns', tags=['marketing']) }}

-- Latest row per campaign_id: greatest _loaded_at, then greatest _run_id as tie-breaker.
with ranked as (
    select
        *,
        row_number() over (
            partition by campaign_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_campaigns') }}
)

select
    campaign_id,
    name,
    channel,
    market,
    start_date,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
