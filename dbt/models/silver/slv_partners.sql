{{ config(alias='partners', tags=['partner_outreach']) }}

-- Latest row per partner_id: greatest _loaded_at, then greatest _run_id as tie-breaker.
with ranked as (
    select
        *,
        row_number() over (
            partition by partner_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_partners') }}
)

select
    partner_id,
    name,
    partner_type,
    country,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
