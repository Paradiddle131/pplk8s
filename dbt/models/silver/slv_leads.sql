{{ config(alias='leads', tags=['marketing']) }}

-- Latest row per lead_id: greatest _loaded_at, then greatest _run_id as tie-breaker.
with ranked as (
    select
        *,
        row_number() over (
            partition by lead_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_leads') }}
)

select
    lead_id,
    campaign_id,
    created_ts,
    {{ utc_date('created_ts') }} as created_date,
    country,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
