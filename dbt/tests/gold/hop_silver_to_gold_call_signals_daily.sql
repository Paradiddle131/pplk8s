{{ config(tags=['gold', 'call_transcripts']) }}

-- Per day, gold's labelled calls, calls with an objection and positive calls over all topics equal
-- silver's labelled calls on the call's day.
{% set upstream %}
    select call_date, count(*) as calls_labelled,
           sum(case when objection <> 'none' then 1 else 0 end) as calls_with_objection,
           sum(case when sentiment = 'positive' then 1 else 0 end) as positive_calls
    from {{ ref('slv_call_signals') }}
    group by call_date
{% endset %}

{% set downstream %}
    select call_date, calls_labelled, calls_with_objection, positive_calls
    from {{ ref('gld_call_signals_daily') }}
{% endset %}

{{ hop_mismatches('silver -> gold call_signals_daily', upstream, downstream, ['call_date'],
                  ['calls_labelled', 'calls_with_objection', 'positive_calls']) }}
