{{ config(tags=['gold', 'marketing']) }}

-- Per day, gold's leads equal silver's leads created that day, and gold has a row for every such day
-- (a day row counts 1 on both sides).
{% set upstream %}
    select created_date, 1 as day_rows, count(*) as leads
    from {{ ref('slv_leads') }}
    group by created_date
{% endset %}

{% set downstream %}
    select created_date, 1 as day_rows, leads
    from {{ ref('gld_lead_conversion_daily') }}
{% endset %}

{{ hop_mismatches('silver -> gold lead_conversion_daily', upstream, downstream, ['created_date'], ['day_rows', 'leads']) }}
