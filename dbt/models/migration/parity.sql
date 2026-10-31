{{ config(alias='parity') }}

-- The parity report of the migration rehearsal (semantic/PLAN.md SL-11): per consumer and field, how
-- many keys its legacy relation and its new model hold, and how many differ. A consumer switches from
-- legacy to new only when every field matches, or its difference is accepted on its exposure
-- (migration/consumers.yml); the test consumers_switch_on_parity fails a build that switches one
-- without it. Each consumer here has its exposure, in the order consumers switch.
with compared as (
    {{ parity_rows(
        'finance_dashboard', ref('lgc_daily_net_sales'), ref('exp_net_sales_daily'),
        keys={'sales_date': 'order_date'},
        fields={'gross_revenue': 'revenue_eur', 'returns_amount': 'returns_eur', 'net_revenue': 'net_revenue_eur'},
    ) }}
    union all
    {{ parity_rows(
        'sales_agent', ref('lgc_country_sales'), ref('exp_sales_by_country_daily'),
        keys={'sales_date': 'order_date', 'country': 'country'},
        fields={'orders': 'orders', 'revenue': 'revenue_eur'},
    ) }}
    union all
    {{ parity_rows(
        'marketing_automation', ref('lgc_channel_daily'), ref('exp_channel_performance_daily'),
        keys={'day': 'activity_date', 'channel': 'channel'},
        fields={
            'spend': 'ad_spend_eur', 'leads': 'leads', 'bookings': 'bookings',
            'cost_per_lead': 'cost_per_lead_eur', 'cost_per_booking': 'cost_per_booking_eur',
        },
    ) }}
)

select
    consumer,
    field,
    legacy_relation,
    new_relation,
    keys_compared,
    keys_differing,
    case when keys_differing = 0 then 'match' else 'differs' end as status
from compared
