{{ config(tags=['silver', 'recruitment']) }}

-- Every stage in the history is one an extract landed, with the same stage_ts, and stages only move
-- forward in time (semantic/PLAN.md SL-17): one row per history row that bronze never landed, or that
-- begins before the row it follows ends. Any row fails the build.
with landed as (
    select distinct candidate_id, stage, stage_ts
    from {{ ref('brz_synthetic_applications') }}
),

history as (
    select
        candidate_id,
        stage,
        valid_from,
        valid_to,
        lag(valid_to) over (partition by candidate_id order by valid_from) as previous_valid_to
    from {{ ref('slv_candidate_stages') }}
)

select h.candidate_id, h.stage, h.valid_from, 'never landed' as problem
from history as h
left join landed as l
    on l.candidate_id = h.candidate_id and l.stage = h.stage and l.stage_ts = h.valid_from
where l.candidate_id is null
union all
select candidate_id, stage, valid_from, 'overlaps the stage before' as problem
from history
where previous_valid_to is not null and previous_valid_to <> valid_from
