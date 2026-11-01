{{ config(alias='recruitment_daily', tags=['recruitment']) }}

-- One row per day with any application or hire: the hand-written daily recruitment aggregate, kept as
-- the parity oracle for the recruitment metrics (semantic/PLAN.md SL-8, SL-17). Applications count
-- on the day the candidate applied, hires and time to hire on the day the candidate was hired.
with applied as (
    select applied_date as recruitment_date, count(*) as applications
    from {{ ref('slv_applications') }}
    group by applied_date
),

hired as (
    select hired_date as recruitment_date, count(*) as hires, avg(days_to_hire) as time_to_hire_days
    from {{ ref('slv_applications') }}
    where current_stage = 'hired'
    group by hired_date
),

days as (
    select recruitment_date from applied
    union distinct
    select recruitment_date from hired
)

select
    d.recruitment_date,
    coalesce(a.applications, 0) as applications,
    coalesce(h.hires, 0) as hires,
    h.time_to_hire_days
from days as d
left join applied as a on a.recruitment_date = d.recruitment_date
left join hired as h on h.recruitment_date = d.recruitment_date
