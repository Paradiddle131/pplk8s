{{ config(alias='returns', tags=['returns']) }}

-- Latest row per return_id across files: greatest _loaded_at, then greatest _generation.
-- reason is conformed to the codes schema.yml declares (#157); bronze keeps the partner's raw value.
-- Codes loaded before that contract map to their conformed code: `late` to `late delivery`, and the
-- markers earlier lab checks uploaded (`check`, `drill`, `drill10`) to the `damaged` they upload now.
-- Any other code fails the accepted_values test, so a new partner code is mapped here or declared there.
with ranked as (
    select
        *,
        row_number() over (
            partition by return_id
            order by _loaded_at desc, _generation desc
        ) as row_rank
    from {{ ref('brz_partner_returns') }}
)

select
    return_id,
    order_id,
    returned_at,
    {{ utc_date('returned_at') }} as return_date,
    amount,
    case reason
        when 'late' then 'late delivery'
        when 'check' then 'damaged'
        when 'drill' then 'damaged'
        when 'drill10' then 'damaged'
        else reason
    end as reason,
    _source_uri,
    _generation,
    _loaded_at
from ranked
where row_rank = 1
