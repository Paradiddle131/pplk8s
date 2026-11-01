{{ config(tags=['gold', 'customer_actions']) }}

-- Per day and action type, gold's actions and customers equal silver's, each action on its event_date.
{% set upstream %}
    select event_date as activity_date, action_type, count(*) as actions, count(distinct customer_id) as customers
    from {{ ref('slv_customer_actions') }}
    group by event_date, action_type
{% endset %}

{% set downstream %}
    select activity_date, action_type, actions, customers
    from {{ ref('gld_customer_actions_daily') }}
{% endset %}

{{ hop_mismatches('silver -> gold customer_actions_daily', upstream, downstream,
                  ['activity_date', 'action_type'], ['actions', 'customers']) }}
