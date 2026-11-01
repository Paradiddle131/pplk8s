{{ config(
    alias='call_golden_labels',
    tags=['call_transcripts'],
    materialized='incremental',
    unique_key=['transcript_id', 'prompt_version'],
    full_refresh=false,
    on_schema_change='fail',
) }}
-- depends_on: {{ ref('call_label_recordings') }}

-- The golden set's calls labelled by the same prompt and path as silver.call_transcript_labels
-- (semantic/PLAN.md SL-18): one row per golden call and prompt version, labelled once, so every
-- prompt version is scored on the same calls whatever days production has landed.
{%- set prompt = var('call_label_prompt') %}

with pending as (
    select g.transcript_id, g.transcript
    from {{ ref('call_label_golden_set') }} as g
    {#- An offline compile (--no-introspect, the compile-only BigQuery target) cannot ask whether the table
        exists, so it compiles the first build. #}
    {%- if flags.INTROSPECT and is_incremental() %}
    where not exists (
        select 1
        from {{ this }} as labelled
        where labelled.transcript_id = g.transcript_id
            and labelled.prompt_version = '{{ prompt.version }}'
            and labelled.status = ''
    )
    {%- endif %}
)

{{ label_calls('pending', prompt) }}
