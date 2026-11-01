{{ config(alias='candidates_in_stage_daily', tags=['recruitment']) }}

-- One row per day and hiring stage with any candidate in it at the end of the day: the hand-written
-- as-of count from the stage history, kept as the parity oracle for candidates_in_stage by stage
-- (semantic/PLAN.md SL-17). A day before a candidate's first snapshot has no stage and no row.
select
    d.calendar_date as stage_date,
    s.stage,
    count(distinct d.candidate_id) as candidates
from {{ ref('slv_candidate_days') }} as d
inner join {{ ref('slv_candidate_stages') }} as s
    on s.candidate_id = d.candidate_id
    and d.calendar_date >= s.valid_from_date
    and (s.valid_to_date is null or d.calendar_date < s.valid_to_date)
group by d.calendar_date, s.stage
