{{ config(tags=['silver', 'partner_outreach']) }}

-- Bronze -> silver for the contact snapshots (semantic/PLAN.md SL-9, SL-16): silver holds one row per
-- contact bronze ever landed, and a contact is opted out in silver exactly when any landed snapshot
-- opted them out, whatever order the snapshots were loaded in.
{% set upstream %}
    select
        count(distinct contact_id) as contacts,
        count(distinct case when opted_out_ts is not null then contact_id end) as opted_out
    from {{ ref('brz_synthetic_partner_contacts') }}
{% endset %}

{% set downstream %}
    select
        count(*) as contacts,
        count(opted_out_ts) as opted_out
    from {{ ref('slv_partner_contacts') }}
{% endset %}

{{ hop_mismatches('bronze -> silver partner_contacts', upstream, downstream, [], ['contacts', 'opted_out']) }}
