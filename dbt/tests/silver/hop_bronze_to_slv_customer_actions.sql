{{ config(tags=['silver', 'customer_actions']) }}

-- The bronze -> silver hop of an append-only stream (semantic/PLAN.md SL-9, SL-15): latest_load_reconciles
-- compares whole tables, which an incremental model should not rescan on every build. Here every event
-- date that bronze's loads of the lookback touched holds as many distinct events in silver as in bronze,
-- whatever load they came in, so a late event that missed the merge, or a redelivery merged twice, fails
-- the build on its event date.
{% set lookback = var('customer_actions_lookback_hours') %}
{% set touched %}
    select distinct {{ utc_date('event_ts') }}
    from {{ ref('brz_synthetic_customer_actions') }}
    where _loaded_at > (
        select {{ hours_before('max(_loaded_at)', lookback) }} from {{ ref('brz_synthetic_customer_actions') }}
    )
{% endset %}

{% set upstream %}
    select {{ utc_date('event_ts') }} as event_date, count(distinct event_id) as events
    from {{ ref('brz_synthetic_customer_actions') }}
    where {{ utc_date('event_ts') }} in ({{ touched }})
    group by {{ utc_date('event_ts') }}
{% endset %}

{% set downstream %}
    select event_date, count(*) as events
    from {{ ref('slv_customer_actions') }}
    where event_date in ({{ touched }})
    group by event_date
{% endset %}

{{ hop_mismatches('bronze -> silver customer_actions', upstream, downstream, ['event_date'], ['events']) }}
