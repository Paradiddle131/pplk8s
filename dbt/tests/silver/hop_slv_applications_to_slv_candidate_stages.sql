{{ config(tags=['silver', 'recruitment']) }}

-- Silver -> the stage history (semantic/PLAN.md SL-9, SL-17): per stage, the candidates whose current
-- stage it is in silver.applications equal the history's open rows (valid_to NULL) in it, so every
-- candidate has exactly one current stage in the history and it is their newest.
{% set upstream %}
    select current_stage as stage, count(*) as candidates
    from {{ ref('slv_applications') }}
    group by current_stage
{% endset %}

{% set downstream %}
    select stage, count(*) as candidates
    from {{ ref('slv_candidate_stages') }}
    where valid_to is null
    group by stage
{% endset %}

{{ hop_mismatches('silver applications -> candidate_stages', upstream, downstream, ['stage'], ['candidates']) }}
