{{ config(alias='call_transcripts', tags=['call_transcripts']) }}

-- Latest row per transcript_id: greatest _loaded_at, then greatest _run_id as tie-breaker.
with ranked as (
    select
        *,
        row_number() over (
            partition by transcript_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_call_transcripts') }}
)

select
    transcript_id,
    customer_id,
    call_ts,
    {{ utc_date('call_ts') }} as call_date,
    duration_seconds,
    transcript,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
