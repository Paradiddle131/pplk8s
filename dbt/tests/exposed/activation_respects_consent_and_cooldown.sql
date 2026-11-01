{{ config(tags=['exposed', 'partner_outreach']) }}

-- The outreach automation acts on exposed.outreach_activation unseen (semantic/PLAN.md SL-16), so the
-- exclusion rule is checked from the bronze history rather than from the model's own logic: one row
-- per listed contact who has ever landed without consent or with an opt-out, or who was messaged
-- within the cooldown before the list's as_of. Any row fails the build.
with listed as (
    select contact_id, as_of from {{ ref('exp_outreach_activation') }}
),

never_reachable as (
    select distinct contact_id, 'no consent or opted out' as problem
    from {{ ref('brz_synthetic_partner_contacts') }}
    where not consent or opted_out_ts is not null
),

recently_contacted as (
    select distinct m.contact_id, 'contacted within the cooldown' as problem
    from {{ ref('brz_synthetic_outreach_messages') }} as m
    inner join listed as l on l.contact_id = m.contact_id
    where m.sent_ts > {{ hours_before('l.as_of', 24 * var('outreach_cooldown_days')) }}
)

select l.contact_id, p.problem
from listed as l
inner join (
    select contact_id, problem from never_reachable
    union all
    select contact_id, problem from recently_contacted
) as p on p.contact_id = l.contact_id
