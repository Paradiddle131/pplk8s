{{ config(alias='outreach_replies', tags=['partner_outreach']) }}

-- Latest row per reply_id, with its message's partner. Replies are extracted per interval and look
-- back past the reply lag, so a reply can name a message sent before the first loaded interval: its
-- tests warn, it keeps no partner, and it counts as a reply but not as an engaged partner.
with ranked as (
    select
        *,
        row_number() over (
            partition by reply_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_outreach_replies') }}
)

select
    r.reply_id,
    r.message_id,
    m.partner_id,
    r.replied_ts,
    {{ utc_date('r.replied_ts') }} as replied_date,
    r._run_id,
    r._loaded_at
from ranked as r
left join {{ ref('slv_outreach_messages') }} as m on m.message_id = r.message_id
where r.row_rank = 1
