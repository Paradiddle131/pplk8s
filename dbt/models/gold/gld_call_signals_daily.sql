{{ config(alias='call_signals_daily', tags=['call_transcripts']) }}

-- One row per (call_date, topic) with any labelled call: the hand-written daily aggregate of the call
-- signals, kept as the parity oracle for their metrics (semantic/PLAN.md SL-18). Model-derived: the
-- topic, objection and sentiment come from the current prompt version's labels (silver.call_signals).
select
    call_date,
    topic,
    count(*) as calls_labelled,
    sum(case when objection <> 'none' then 1 else 0 end) as calls_with_objection,
    sum(case when sentiment = 'positive' then 1 else 0 end) as positive_calls
from {{ ref('slv_call_signals') }}
group by call_date, topic
