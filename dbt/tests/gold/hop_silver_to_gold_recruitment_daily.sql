{{ config(tags=['gold', 'recruitment']) }}

-- Per day, gold's applications equal silver's on the applied date, and its hires silver's hired
-- candidates on the hired date.
{% set upstream %}
    select recruitment_date, sum(applications) as applications, sum(hires) as hires
    from (
        select applied_date as recruitment_date, count(*) as applications, 0 as hires
        from {{ ref('slv_applications') }}
        group by applied_date
        union all
        select hired_date, 0, count(*)
        from {{ ref('slv_applications') }}
        where hired_date is not null
        group by hired_date
    ) as days
    group by recruitment_date
{% endset %}

{% set downstream %}
    select recruitment_date, applications, hires
    from {{ ref('gld_recruitment_daily') }}
{% endset %}

{{ hop_mismatches('silver -> gold recruitment_daily', upstream, downstream,
                  ['recruitment_date'], ['applications', 'hires']) }}
