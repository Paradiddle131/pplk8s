{{ config(alias='synthetic_orders', tags=['sales']) }}

select
    cast(order_id as {{ dbt.type_string() }}) as order_id,
    cast(customer_id as integer) as customer_id,
    cast(order_ts as {{ type_timestamptz() }}) as order_ts,
    cast(status as {{ dbt.type_string() }}) as status,
    cast(amount as numeric(12,2)) as amount,
    cast(currency as {{ dbt.type_string() }}) as currency,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_orders') }}
