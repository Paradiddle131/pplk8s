{{ config(alias='customers', tags=['sales']) }}

-- Latest row per customer_id: greatest _loaded_at, then greatest _run_id as tie-breaker.
with ranked as (
    select
        *,
        row_number() over (
            partition by customer_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_customers') }}
)

select
    customer_id,
    name,
    email,
    country,
    signup_date,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
