{{ config(tags=['gold', 'recruitment']) }}

-- Per day and stage, gold's candidates equal the candidates whose stage history row covers the end of
-- that day, counted from the history and each candidate's applied date rather than silver.candidate_days.
{% set upstream %}
    select d.date_day as stage_date, s.stage, count(*) as candidates
    from {{ ref('slv_candidate_stages') }} as s
    inner join {{ ref('slv_applications') }} as a on a.candidate_id = s.candidate_id
    cross join (
        select max({{ utc_date('_interval_end') }}) as last_loaded_end
        from {{ ref('brz_synthetic_applications') }}
    ) as l
    inner join ({{ day_spine('2024-01-01', '2027-12-31') }}) as d
        on d.date_day >= s.valid_from_date
        and (s.valid_to_date is null or d.date_day < s.valid_to_date)
        and d.date_day >= a.applied_date
        and d.date_day < l.last_loaded_end
    group by d.date_day, s.stage
{% endset %}

{% set downstream %}
    select stage_date, stage, candidates
    from {{ ref('gld_candidates_in_stage_daily') }}
{% endset %}

{{ hop_mismatches('silver -> gold candidates_in_stage_daily', upstream, downstream,
                  ['stage_date', 'stage'], ['candidates']) }}
