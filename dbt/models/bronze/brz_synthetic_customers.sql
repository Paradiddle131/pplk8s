{{ config(alias='synthetic_customers', tags=['sales']) }}

select
    cast(customer_id as integer) as customer_id,
    cast(name as {{ dbt.type_string() }}) as name,
    cast(email as {{ dbt.type_string() }}) as email,
    cast(country as {{ dbt.type_string() }}) as country,
    cast(signup_date as date) as signup_date,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_customers') }}
