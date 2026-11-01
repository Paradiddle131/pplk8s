{{ config(alias='call_label_agreement', tags=['call_transcripts']) }}

-- Agreement of each prompt version's labels of the golden set's calls with its true labels, per signal (semantic/PLAN.md SL-18):
-- the calls compared, the share labelled as the golden set says (accuracy), and Cohen's kappa, the
-- agreement beyond what chance would give with the same label shares: (p_o - p_e) / (1 - p_e), where
-- p_e sums, over the values, the labels' share times the golden set's share. Kappa is NULL when both
-- sides use one value only. The current version's thresholds come from `call_label_prompt`; the test
-- call_labels_agree_with_golden_set fails the build below them. Failed calls are left out here and
-- counted by the failed_call_share test.
{%- set prompt = var('call_label_prompt') %}
{%- set signals = ['topic', 'objection', 'sentiment', 'next_step'] %}
{%- set numeric = dbt.type_numeric() %}

with pairs as (
    {%- for signal in signals %}
    select l.prompt_version, '{{ signal }}' as signal, l.{{ signal }} as labelled, g.{{ signal }} as golden
    from {{ ref('slv_call_golden_labels') }} as l
    inner join {{ ref('call_label_golden_set') }} as g on g.transcript_id = l.transcript_id
    where l.status = ''
    {{ 'union all' if not loop.last }}
    {%- endfor %}
),

totals as (
    select
        prompt_version,
        signal,
        count(*) as calls_compared,
        sum(case when labelled = golden then 1 else 0 end) as calls_agreed
    from pairs
    group by prompt_version, signal
),

labelled_counts as (
    select prompt_version, signal, labelled as label_value, count(*) as calls
    from pairs
    group by prompt_version, signal, labelled
),

golden_counts as (
    select prompt_version, signal, golden as label_value, count(*) as calls
    from pairs
    group by prompt_version, signal, golden
),

chance as (
    select
        l.prompt_version,
        l.signal,
        sum(cast(l.calls as {{ numeric }}) * g.calls) as chance_pairs
    from labelled_counts as l
    inner join golden_counts as g
        on g.prompt_version = l.prompt_version and g.signal = l.signal and g.label_value = l.label_value
    group by l.prompt_version, l.signal
),

scored as (
    select
        t.prompt_version,
        t.signal,
        t.calls_compared,
        cast(t.calls_agreed as {{ numeric }}) / t.calls_compared as accuracy,
        coalesce(c.chance_pairs, 0) / (cast(t.calls_compared as {{ numeric }}) * t.calls_compared) as chance_agreement
    from totals as t
    left join chance as c on c.prompt_version = t.prompt_version and c.signal = t.signal
)

select
    prompt_version,
    signal,
    calls_compared,
    round(accuracy, 4) as accuracy,
    case
        when chance_agreement < 1 then round((accuracy - chance_agreement) / (1 - chance_agreement), 4)
    end as kappa,
    case prompt_version
        when '{{ prompt.version }}' then case signal
            {%- for signal in signals %}
            when '{{ signal }}' then cast({{ prompt.thresholds[signal].accuracy }} as {{ numeric }})
            {%- endfor %}
        end
    end as min_accuracy,
    case prompt_version
        when '{{ prompt.version }}' then case signal
            {%- for signal in signals %}
            when '{{ signal }}' then cast({{ prompt.thresholds[signal].kappa }} as {{ numeric }})
            {%- endfor %}
        end
    end as min_kappa
from scored
