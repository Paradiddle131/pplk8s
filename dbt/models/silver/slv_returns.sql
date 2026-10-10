{{ config(alias='returns', tags=['returns']) }}

-- Latest row per return_id across files: greatest _loaded_at, then greatest _generation.
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
    -- dialect: Postgres converts the timestamptz to UTC with AT TIME ZONE; BigQuery uses DATE(returned_at, 'UTC').
    cast(returned_at at time zone 'UTC' as date) as return_date,
    amount,
    reason,
    _source_uri,
    _generation,
    _loaded_at
from ranked
where row_rank = 1
