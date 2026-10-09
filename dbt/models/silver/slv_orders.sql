{{ config(alias='orders') }}

-- Latest row per order_id: greatest _loaded_at, then greatest _run_id as tie-breaker.
with ranked as (
    select
        *,
        row_number() over (
            partition by order_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_orders') }}
)

select
    order_id,
    customer_id,
    order_ts,
    -- dialect: Postgres converts the timestamptz to UTC with AT TIME ZONE; BigQuery uses DATE(order_ts, 'UTC').
    cast(order_ts at time zone 'UTC' as date) as order_date,
    status,
    amount,
    currency,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
