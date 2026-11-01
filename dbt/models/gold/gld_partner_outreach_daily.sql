{{ config(alias='partner_outreach_daily', tags=['partner_outreach']) }}

-- One row per day with any outreach message sent or reply received: the hand-written daily outreach
-- aggregate, kept as the parity oracle for the outreach metrics (semantic/PLAN.md SL-8). Messages
-- and the ones replied to count on the day they were sent, replies and engaged partners on the day
-- the reply arrived; a reply whose message is not loaded counts as a reply, not as a partner.
with sent as (
    select
        sent_date as outreach_date,
        count(*) as messages_sent,
        count(first_replied_ts) as messages_replied
    from {{ ref('slv_outreach_messages') }}
    group by sent_date
),

replied as (
    select
        replied_date as outreach_date,
        count(*) as replies,
        count(distinct partner_id) as partners_engaged
    from {{ ref('slv_outreach_replies') }}
    group by replied_date
),

days as (
    select outreach_date from sent
    union distinct
    select outreach_date from replied
)

select
    d.outreach_date,
    coalesce(s.messages_sent, 0) as messages_sent,
    coalesce(s.messages_replied, 0) as messages_replied,
    coalesce(r.replies, 0) as replies,
    coalesce(r.partners_engaged, 0) as partners_engaged,
    cast(s.messages_replied as {{ dbt.type_numeric() }}) / nullif(s.messages_sent, 0) as reply_rate
from days as d
left join sent as s on s.outreach_date = d.outreach_date
left join replied as r on r.outreach_date = d.outreach_date
