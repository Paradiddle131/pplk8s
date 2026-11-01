{{ config(alias='returns', tags=['returns']) }}

-- Latest row per return_id across files: greatest _loaded_at, then greatest _generation.
-- reason is conformed to the codes schema.yml declares (#157); bronze keeps the partner's raw value.
-- Codes loaded before that contract map to their conformed code: `late` to `late delivery`, and the
-- markers earlier lab checks uploaded (`check`, `drill`, `drill10`) to the `damaged` they upload now.
-- Any other code fails the accepted_values test, so a new partner code is mapped here or declared there.
-- customer_id is the returned order's customer, so returns reach the customer by the same path as the
-- order's revenue and net revenue groups by customer country; empty while the order is not in silver.
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
    r.return_id,
    r.order_id,
    o.customer_id,
    r.returned_at,
    {{ utc_date('r.returned_at') }} as return_date,
    r.amount,
    case r.reason
        when 'late' then 'late delivery'
        when 'check' then 'damaged'
        when 'drill' then 'damaged'
        when 'drill10' then 'damaged'
        else r.reason
    end as reason,
    r._source_uri,
    r._generation,
    r._loaded_at
from ranked as r
left join {{ ref('slv_orders') }} as o
    on o.order_id = r.order_id
where r.row_rank = 1
