{{ config(tags=['gold', 'partner_outreach']) }}

-- Per day, gold's messages sent and replied equal silver's on the sent date, and its replies and
-- engaged partners equal silver's on the reply date.
{% set upstream %}
    select outreach_date, sum(messages_sent) as messages_sent, sum(messages_replied) as messages_replied,
           sum(replies) as replies, sum(partners_engaged) as partners_engaged
    from (
        select sent_date as outreach_date, count(*) as messages_sent, count(first_replied_ts) as messages_replied,
               0 as replies, 0 as partners_engaged
        from {{ ref('slv_outreach_messages') }}
        group by sent_date
        union all
        select replied_date, 0, 0, count(*), count(distinct partner_id)
        from {{ ref('slv_outreach_replies') }}
        group by replied_date
    ) as days
    group by outreach_date
{% endset %}

{% set downstream %}
    select outreach_date, messages_sent, messages_replied, replies, partners_engaged
    from {{ ref('gld_partner_outreach_daily') }}
{% endset %}

{{ hop_mismatches('silver -> gold partner_outreach_daily', upstream, downstream,
                  ['outreach_date'], ['messages_sent', 'messages_replied', 'replies', 'partners_engaged']) }}
