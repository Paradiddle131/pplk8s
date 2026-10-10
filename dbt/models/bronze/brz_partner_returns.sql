{{ config(alias='partner_returns', tags=['returns']) }}

-- One row per return line of every landed file; a newer generation of an object replaces its rows
-- in ds_source (EL Factory POST /load), so bronze never holds two generations of the same file.
select
    cast(return_id as text) as return_id,
    cast(order_id as text) as order_id,
    cast(returned_at as timestamptz) as returned_at,
    cast(amount as numeric(12, 2)) as amount,
    cast(reason as text) as reason,
    _run_id,
    _source_uri,
    _generation,
    _loaded_at
from {{ source('ds_source', 'partner_returns') }}
