{{ config(
    alias='tlc_trips',
    tags=['tlc'],
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='data_month',
    on_schema_change='append_new_columns',
    indexes=[{'columns': ['data_month']}],
) }}

-- Clean yellow and green trips, one data month replaced per build (D36): delete+insert on
-- data_month swaps the whole month, so a republished file (new etag) replaces its month and a
-- rebuild never duplicates. TLC rows have no natural key; the file version is the dedup unit.
-- dialect: BigQuery uses insert_overwrite on a month-partitioned pickup_date instead.
select
    trip_type,
    data_month,
    {%- for column in tlc_columns() %}
    {{ column.name }},
    {%- endfor %}
    _run_id,
    _source_uri,
    _etag,
    _loaded_at
from {{ ref('slv_tlc_trips_checked') }}
where quarantine_reason is null
