{{ config(tags=['silver', 'call_transcripts']) }}

-- Drift no data shows (semantic/PLAN.md SL-18): every model version that labelled calls under the current
-- prompt version has labelled the golden set under it too, so its agreement was scored before a metric reads
-- its labels. A model behind the same endpoint that moves to a new version fails the build here; the way on is
-- a new prompt version, labelled and scored beside the old one (docs/text-signals.md § Versioning).
-- A NULL model_version (the response named none) matches only a NULL on the golden side.
{%- set version = var('call_label_prompt').version %}

select l.prompt_version, l.model_version, count(*) as calls
from {{ ref('slv_call_transcript_labels') }} as l
where l.prompt_version = '{{ version }}'
    and l.status = ''
    and not exists (
        select 1
        from {{ ref('slv_call_golden_labels') }} as g
        where g.prompt_version = l.prompt_version
            and g.status = ''
            and coalesce(g.model_version, '') = coalesce(l.model_version, '')
    )
group by l.prompt_version, l.model_version
