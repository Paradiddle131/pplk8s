{{ config(alias='outreach_messages', tags=['partner_outreach']) }}

-- Latest row per message_id, with its contact's partner and when its first reply arrived. Replies
-- come from bronze, not slv_outreach_replies, which reads this model for the partner of each reply.
-- A reply can arrive days after its message, so first_replied_ts fills in on a later run.
with ranked as (
    select
        *,
        row_number() over (
            partition by message_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_outreach_messages') }}
),

first_replies as (
    select message_id, min(replied_ts) as first_replied_ts
    from {{ ref('brz_synthetic_outreach_replies') }}
    group by message_id
)

select
    m.message_id,
    m.contact_id,
    c.partner_id,
    m.channel,
    m.sent_ts,
    {{ utc_date('m.sent_ts') }} as sent_date,
    r.first_replied_ts,
    m._run_id,
    m._loaded_at
from ranked as m
left join {{ ref('slv_partner_contacts') }} as c on c.contact_id = m.contact_id
left join first_replies as r on r.message_id = m.message_id
where m.row_rank = 1
