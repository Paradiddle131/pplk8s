{{ config(tags=['silver', 'recruitment']) }}

-- Bronze -> silver for the recruitment extracts (semantic/PLAN.md SL-9, SL-17): silver holds one row per
-- candidate bronze ever landed, and a candidate is hired or rejected in silver exactly when any landed
-- extract closed them, whatever order the extracts were loaded in (a closed stage is final).
{% set upstream %}
    select
        count(distinct candidate_id) as candidates,
        count(distinct case when stage = 'hired' then candidate_id end) as hired,
        count(distinct case when stage = 'rejected' then candidate_id end) as rejected
    from {{ ref('brz_synthetic_applications') }}
{% endset %}

{% set downstream %}
    select
        count(*) as candidates,
        count(case when current_stage = 'hired' then 1 end) as hired,
        count(case when current_stage = 'rejected' then 1 end) as rejected
    from {{ ref('slv_applications') }}
{% endset %}

{{ hop_mismatches('bronze -> silver applications', upstream, downstream, [], ['candidates', 'hired', 'rejected']) }}
