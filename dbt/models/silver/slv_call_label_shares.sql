{{ config(alias='call_label_shares', tags=['call_transcripts']) }}

-- Drift the data shows (semantic/PLAN.md SL-18, docs/text-signals.md § Testing the labels): per signal, label
-- and ISO week, the share of the current prompt version's labelled calls that got the label, against the
-- share the trailing weeks expect. The band is a p-chart's: the trailing weeks' pooled share p, plus or minus
-- `sigmas` binomial standard errors for this week's count of calls, sqrt(p * (1 - p) / calls), clipped to
-- [0, 1]; it is NULL until `min_trailing_weeks` weeks with calls precede the week. A label the trailing weeks
-- never gave has a band of [0, 0], so its first appearance is outside it. Every label a signal has ever been
-- given gets a row each week, 0 when unused, so a label that stops appearing shows too.
-- The warehouse's sql_exporter exports the newest week (platform/compose/sql-exporter/call-label-shares.collector.yml),
-- and CallLabelShareDrift alerts on a share outside its band. The parameters are dbt_project.yml's `call_label_drift`.
{%- set drift = var('call_label_drift') %}
{%- set signals = ['topic', 'objection', 'sentiment', 'next_step'] %}
{%- set numeric = dbt.type_numeric() %}

with labels as (
    {%- for signal in signals %}
    select {{ iso_week_start('call_date') }} as week_start, '{{ signal }}' as signal, {{ signal }} as label
    from {{ ref('slv_call_signals') }}
    {{ 'union all' if not loop.last }}
    {%- endfor %}
),

week_totals as (
    select signal, week_start, count(label) as week_calls
    from labels
    group by signal, week_start
    having count(label) > 0
),

label_values as (
    select distinct signal, label
    from labels
    where label is not null
),

counts as (
    select signal, week_start, label, count(*) as calls
    from labels
    where label is not null
    group by signal, week_start, label
),

grid as (
    select t.signal, v.label, t.week_start, t.week_calls, coalesce(c.calls, 0) as calls
    from week_totals as t
    inner join label_values as v on v.signal = t.signal
    left join counts as c on c.signal = t.signal and c.week_start = t.week_start and c.label = v.label
),

windowed as (
    select
        signal,
        label,
        week_start,
        week_calls,
        calls,
        count(*) over (
            partition by signal, label order by week_start
            rows between {{ drift.trailing_weeks }} preceding and 1 preceding
        ) as trailing_weeks,
        sum(calls) over (
            partition by signal, label order by week_start
            rows between {{ drift.trailing_weeks }} preceding and 1 preceding
        ) as trailing_calls,
        sum(week_calls) over (
            partition by signal, label order by week_start
            rows between {{ drift.trailing_weeks }} preceding and 1 preceding
        ) as trailing_week_calls
    from grid
),

expected as (
    select
        signal,
        label,
        week_start,
        week_calls,
        calls,
        trailing_weeks,
        cast(calls as {{ numeric }}) / week_calls as share,
        case
            when trailing_weeks >= {{ drift.min_trailing_weeks }}
                then cast(trailing_calls as {{ numeric }}) / trailing_week_calls
        end as expected_share
    from windowed
),

banded as (
    select
        *,
        {{ drift.sigmas }} * sqrt(expected_share * (1 - expected_share) / week_calls) as half_width
    from expected
)

select
    signal,
    label,
    week_start,
    week_calls,
    calls,
    round(share, 4) as share,
    trailing_weeks,
    round(expected_share, 4) as expected_share,
    {#- Postgres' greatest and least skip a NULL argument, so the band is NULL only through the case. #}
    case when half_width is not null
        then round(greatest(cast(0 as {{ numeric }}), expected_share - half_width), 4) end as lower_bound,
    case when half_width is not null
        then round(least(cast(1 as {{ numeric }}), expected_share + half_width), 4) end as upper_bound
from banded
