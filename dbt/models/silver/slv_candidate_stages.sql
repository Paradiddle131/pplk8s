{{ config(alias='candidate_stages', tags=['recruitment']) }}

-- The snapshot's stage history in the semantic layer's terms (semantic/PLAN.md SL-17): one row per
-- stage a candidate was in, valid from valid_from to valid_to. The dates are the UTC days the stage
-- began and ended, so a candidate counts in the stage they were in at the end of a day: a stage
-- entered and left on the same day never counts.
select
    candidate_id,
    current_stage as stage,
    dbt_valid_from as valid_from,
    dbt_valid_to as valid_to,
    {{ utc_date('dbt_valid_from') }} as valid_from_date,
    {{ utc_date('dbt_valid_to') }} as valid_to_date
from {{ ref('snp_candidate_stages') }}
