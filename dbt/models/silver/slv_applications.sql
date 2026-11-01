{{ config(alias='applications', tags=['recruitment']) }}

-- One row per candidate in their newest stage: the latest stage_ts wins, then the latest load, so a
-- backfill that lands an older extract last never moves a candidate back (semantic/PLAN.md SL-17).
-- The source keeps no stage history; snp_candidate_stages snapshots this model after every build.
with ranked as (
    select
        *,
        row_number() over (
            partition by candidate_id
            order by stage_ts desc, _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_applications') }}
)

select
    candidate_id,
    role,
    channel,
    applied_ts,
    {{ utc_date('applied_ts') }} as applied_date,
    stage as current_stage,
    stage_ts,
    case when stage = 'hired' then {{ utc_date('stage_ts') }} end as hired_date,
    case when stage = 'hired' then {{ days_between('applied_ts', 'stage_ts') }} end as days_to_hire,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
