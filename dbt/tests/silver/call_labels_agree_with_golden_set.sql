{{ config(tags=['silver', 'call_transcripts']) }}

-- The current prompt version's labels agree with the golden set at least as well as the thresholds
-- written beside the prompt (dbt_project.yml `call_label_prompt`, semantic/PLAN.md SL-18): one row per
-- signal below its accuracy or kappa, and one when no golden call was labelled at all, so gold never
-- reads labels nobody scored.
{%- set version = var('call_label_prompt').version %}

select prompt_version, signal, calls_compared, accuracy, min_accuracy, kappa, min_kappa
from {{ ref('slv_call_label_agreement') }}
where prompt_version = '{{ version }}'
    and (accuracy < min_accuracy or kappa < min_kappa)
union all
select '{{ version }}', 'no golden call labelled', 0, null, null, null, null
from (select count(*) as compared from {{ ref('slv_call_label_agreement') }} where prompt_version = '{{ version }}') as c
where c.compared = 0
