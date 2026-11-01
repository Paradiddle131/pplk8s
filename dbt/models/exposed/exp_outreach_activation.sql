{{ config(alias='outreach_activation', tags=['partner_outreach']) }}

-- The outreach automation's activation list (semantic/PLAN.md SL-16): one row per partner contact to
-- contact next, with the contact details the automation needs. A contact is left out when they never
-- consented, have opted out, or were messaged within the cooldown (var outreach_cooldown_days) before
-- as_of, the newest message sent: the stream's own clock, so a rebuild of old data lists what the
-- automation would have seen then. The test activation_respects_consent_and_cooldown fails the build
-- if an excluded contact appears. The model holds personal data: protected, never in the agent catalog.
with last_contacted as (
    select contact_id, max(sent_ts) as last_contacted_at
    from {{ ref('slv_outreach_messages') }}
    group by contact_id
),

as_of as (
    select max(sent_ts) as as_of from {{ ref('slv_outreach_messages') }}
)

select
    c.contact_id,
    c.partner_id,
    p.name as partner_name,
    c.contact_name,
    c.email,
    c.phone,
    c.preferred_channel,
    l.last_contacted_at,
    a.as_of
from {{ ref('slv_partner_contacts') }} as c
inner join {{ ref('slv_partners') }} as p on p.partner_id = c.partner_id
cross join as_of as a
left join last_contacted as l on l.contact_id = c.contact_id
where c.reachable
    and (
        l.last_contacted_at is null
        or l.last_contacted_at <= {{ hours_before('a.as_of', 24 * var('outreach_cooldown_days')) }}
    )
