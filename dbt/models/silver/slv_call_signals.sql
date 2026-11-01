{{ config(alias='call_signals', tags=['call_transcripts']) }}

-- One row per call labelled under the current prompt version (dbt_project.yml `call_label_prompt`):
-- the signals the semantic layer counts, with the call's day and customer. A call whose label call
-- failed, or that waits for one, is left out until it is labelled.
select
    t.transcript_id,
    t.customer_id,
    t.call_date,
    l.topic,
    l.objection,
    l.sentiment,
    l.next_step,
    l.prompt_version,
    l.endpoint,
    l.model_version,
    l.labelled_at
from {{ ref('slv_call_transcripts') }} as t
inner join {{ ref('slv_call_transcript_labels') }} as l
    on l.transcript_id = t.transcript_id
where l.prompt_version = '{{ var('call_label_prompt').version }}'
    and l.status = ''
