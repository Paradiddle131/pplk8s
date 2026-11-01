-- The label call over call transcripts (semantic/PLAN.md SL-18, docs/text-signals.md): a SELECT over
-- `transcripts` (transcript_id, transcript) returning one row per transcript with the prompt version,
-- the endpoint asked, the model version that answered, the four labels, the call's status ('' on
-- success, as AI.GENERATE reports it) and when it was labelled.
-- `var('call_labels')` picks the path: `generated` asks BigQuery's AI.GENERATE; `recorded` joins the
-- lab's recordings (seeds/silver/call_label_recordings.csv, written by scripts/record_call_labels.py),
-- keyed by the transcript's hash and the prompt version, so a transcript without a recording waits
-- unlabelled, as a failed call would. Unset, BigQuery generates (the compile-only `bigquery` output, as at
-- work), except on the emulator, which fakes AI.CLASSIFY and lacks AI.GENERATE (docs/text-signals.md), and on
-- `gcp`, the $0.00 lab project, which may not call Vertex AI (platform/gcp/free-path.yaml lists it as paid);
-- Postgres has no model to ask.
{% macro label_calls(transcripts, prompt) -%}
    {%- set default = 'generated' if target.type == 'bigquery' and target.name not in ('bigquery_emulator', 'gcp') else 'recorded' %}
    {%- set path = var('call_labels', default) %}
    {%- if path == 'generated' %}
        {{ return(adapter.dispatch('generated_call_labels')(transcripts, prompt)) }}
    {%- elif path == 'recorded' %}
        {{ return(recorded_call_labels(transcripts, prompt)) }}
    {%- else %}
        {{ exceptions.raise_compiler_error("label_calls: var call_labels is " ~ path ~ ", not generated or recorded") }}
    {%- endif %}
{%- endmacro %}

{% macro recorded_call_labels(transcripts, prompt) -%}
select
    t.transcript_id,
    r.prompt_version,
    r.endpoint,
    r.model_version,
    r.topic,
    r.objection,
    r.sentiment,
    r.next_step,
    coalesce(r.status, '') as status,
    r.recorded_at as labelled_at
from {{ transcripts }} as t
inner join {{ ref('call_label_recordings') }} as r
    on r.transcript_hash = {{ dbt.hash('t.transcript') }}
    and r.prompt_version = '{{ prompt.version }}'
{%- endmacro %}

{% macro default__generated_call_labels(transcripts, prompt) -%}
    {{ exceptions.raise_compiler_error("label_calls: " ~ target.type ~ " has no model to ask; set var call_labels: recorded") }}
{%- endmacro %}

-- AI.GENERATE with an output schema (stated, not run: the lab's $0.00 project may not call Vertex).
-- The endpoint is always named, never left to BigQuery's choice; temperature 0 and no thinking budget
-- keep the answers as repeatable and as cheap as the model allows.
{% macro bigquery__generated_call_labels(transcripts, prompt) -%}
select
    transcript_id,
    '{{ prompt.version }}' as prompt_version,
    '{{ prompt.endpoint }}' as endpoint,
    json_value(labelled.full_response, '$.modelVersion') as model_version,
    labelled.topic,
    labelled.objection,
    labelled.sentiment,
    labelled.next_step,
    coalesce(labelled.status, '') as status,
    current_timestamp() as labelled_at
from (
    select
        transcript_id,
        AI.GENERATE(
            concat('{{ dbt.escape_single_quotes(prompt.text) }}\n', transcript),
            endpoint => '{{ prompt.endpoint }}',
            output_schema => 'topic STRING, objection STRING, sentiment STRING, next_step STRING',
            model_params => JSON '{"generationConfig": {"temperature": 0, "thinkingConfig": {"thinkingBudget": 0}}}'
        ) as labelled
    from {{ transcripts }}
) as calls
{%- endmacro %}
