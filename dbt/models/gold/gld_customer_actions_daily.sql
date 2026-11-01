{{ config(alias='customer_actions_daily', tags=['customer_actions']) }}

-- One row per (activity_date, action_type): the hand-written daily count of actions per type, kept as
-- the parity oracle for the customer-actions metrics (semantic/PLAN.md SL-8). An action counts on the
-- day it happened, so one that arrived a day late adds to its own, earlier day.
select
    event_date as activity_date,
    action_type,
    channel,
    count(*) as actions,
    count(distinct customer_id) as customers
from {{ ref('slv_customer_actions') }}
group by event_date, action_type, channel
