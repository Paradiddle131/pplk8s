{{ config(alias='synthetic_call_transcripts', tags=['call_transcripts']) }}

select
    cast(transcript_id as {{ dbt.type_string() }}) as transcript_id,
    cast(customer_id as integer) as customer_id,
    cast(call_ts as {{ type_timestamptz() }}) as call_ts,
    cast(duration_seconds as integer) as duration_seconds,
    cast(transcript as {{ dbt.type_string() }}) as transcript,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_call_transcripts') }}
