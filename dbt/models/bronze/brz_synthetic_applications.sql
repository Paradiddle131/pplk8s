{{ config(alias='synthetic_applications', tags=['recruitment']) }}

select
    cast(candidate_id as {{ dbt.type_string() }}) as candidate_id,
    cast(role as {{ dbt.type_string() }}) as role,
    cast(channel as {{ dbt.type_string() }}) as channel,
    cast(applied_ts as {{ type_timestamptz() }}) as applied_ts,
    cast(stage as {{ dbt.type_string() }}) as stage,
    cast(stage_ts as {{ type_timestamptz() }}) as stage_ts,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'synthetic_applications') }}
