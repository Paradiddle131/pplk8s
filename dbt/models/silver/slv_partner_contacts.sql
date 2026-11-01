{{ config(alias='partner_contacts', tags=['partner_outreach']) }}

-- Latest state per contact_id by when the source changed it (updated_ts), then the latest load.
-- Each run lands a snapshot of every contact, so a backfill of an older interval lands an older
-- snapshot after a newer one: ordering by load alone would undo an opt-out the CRM already holds
-- (semantic/PLAN.md SL-16). An opt-out is never withdrawn in the source, so the newest change wins.
with ranked as (
    select
        *,
        row_number() over (
            partition by contact_id
            order by updated_ts desc, _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_partner_contacts') }}
)

select
    contact_id,
    partner_id,
    contact_name,
    email,
    phone,
    preferred_channel,
    consent,
    opted_out_ts,
    consent and opted_out_ts is null as reachable,
    updated_ts,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
