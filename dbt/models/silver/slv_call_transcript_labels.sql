{{ config(
    alias='call_transcript_labels',
    tags=['call_transcripts'],
    materialized='incremental',
    unique_key=['transcript_id', 'prompt_version'],
    full_refresh=false,
    on_schema_change='fail',
) }}
-- depends_on: {{ ref('call_label_recordings') }}

-- One row per transcript and prompt version (semantic/PLAN.md SL-18, docs/text-signals.md): the labels
-- the prompt in dbt_project.yml's `call_label_prompt` got back, or the call's error in `status`. A build
-- sends only transcripts without a successful label for the current version, so a failed call is retried
-- and a labelled one is never sent again; `full_refresh: false` keeps a routine `--full-refresh` from
-- re-sending the whole history and getting different answers back.
{%- set prompt = var('call_label_prompt') %}

with pending as (
    select t.transcript_id, t.transcript
    from {{ ref('slv_call_transcripts') }} as t
    {%- if is_incremental() %}
    where not exists (
        select 1
        from {{ this }} as labelled
        where labelled.transcript_id = t.transcript_id
            and labelled.prompt_version = '{{ prompt.version }}'
            and labelled.status = ''
    )
    {%- endif %}
)

{{ label_calls('pending', prompt) }}
