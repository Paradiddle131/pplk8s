{{ config(alias='customer_engagement_daily', tags=['customer_actions']) }}

-- One row per day with any action: engaged customers over the trailing 7 and 28 days, and the site
-- funnel, hand-written as the parity oracle for the cumulative and conversion metrics (SL-8, SL-15).
-- A trailing window is the day and the days before it, fewer than the window's length. A funnel step
-- converts when its session takes the next step on the same day or the next one, and counts on the
-- day of the step before; each step happens at most once per session (silver's test).
with actions as (
    select * from {{ ref('slv_customer_actions') }}
),

days as (
    select distinct event_date as activity_date from actions
),

engaged as (
    select
        d.activity_date,
        count(distinct case
            when a.event_date > {{ days_before('d.activity_date', 7) }} then a.customer_id
        end) as engaged_customers_7d,
        count(distinct a.customer_id) as engaged_customers_28d
    from days as d
    inner join actions as a
        on a.event_date <= d.activity_date and a.event_date > {{ days_before('d.activity_date', 28) }}
    group by d.activity_date
),

steps as (
    select session_id, action_type, event_date
    from actions
    where session_id is not null
),

-- Each step that has a next step, with the session's next step if it came within the window.
converted as (
    select
        s.event_date as activity_date,
        s.action_type,
        count(distinct s.session_id) as sessions,
        count(distinct n.session_id) as converted
    from steps as s
    left join steps as n
        on n.session_id = s.session_id
        and n.action_type = case s.action_type when 'page_view' then 'add_to_cart' else 'checkout' end
        and s.event_date <= n.event_date
        and s.event_date > {{ days_before('n.event_date', 2) }}
    where s.action_type in ('page_view', 'add_to_cart')
    group by s.event_date, s.action_type
),

sessions as (
    select
        event_date as activity_date,
        count(distinct case when action_type = 'page_view' then session_id end) as site_sessions,
        count(distinct case when action_type = 'add_to_cart' then session_id end) as cart_sessions,
        count(distinct case when action_type = 'checkout' then session_id end) as checkout_sessions
    from steps
    group by event_date
)

select
    d.activity_date,
    e.engaged_customers_7d,
    e.engaged_customers_28d,
    coalesce(s.site_sessions, 0) as site_sessions,
    coalesce(s.cart_sessions, 0) as cart_sessions,
    coalesce(s.checkout_sessions, 0) as checkout_sessions,
    cast(v.converted as {{ dbt.type_numeric() }}) / nullif(v.sessions, 0) as view_to_cart_rate,
    cast(c.converted as {{ dbt.type_numeric() }}) / nullif(c.sessions, 0) as cart_to_checkout_rate
from days as d
inner join engaged as e on e.activity_date = d.activity_date
left join sessions as s on s.activity_date = d.activity_date
left join converted as v on v.activity_date = d.activity_date and v.action_type = 'page_view'
left join converted as c on c.activity_date = d.activity_date and c.action_type = 'add_to_cart'
