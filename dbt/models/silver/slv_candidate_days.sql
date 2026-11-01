{{ config(alias='candidate_days', tags=['recruitment']) }}

-- One row per candidate per UTC day from the day they applied to the last day loaded (the newest
-- extract's interval), the grain the stage counts are asked at (semantic/PLAN.md SL-17): the
-- semantic layer joins each day to the stage valid on it in silver.candidate_stages.
with last_day as (
    select max({{ utc_date('_interval_end') }}) as last_loaded_end
    from {{ ref('brz_synthetic_applications') }}
),

days as (
    {{ day_spine('2024-01-01', '2027-12-31') }}
)

select
    a.candidate_id,
    d.date_day as calendar_date
from {{ ref('slv_applications') }} as a
cross join last_day as l
inner join days as d
    on d.date_day >= a.applied_date
    and d.date_day < l.last_loaded_end
