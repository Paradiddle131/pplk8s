{{ config(
    alias='tlc_trips_quarantine',
    tags=['tlc'],
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='data_month',
    on_schema_change='append_new_columns',
    indexes=[{'columns': ['data_month']}],
) }}

-- Trips that broke a quarantine rule (D36), kept with the rule instead of dropped so bad rows stay
-- countable: per month, bronze (latest completed version) = silver + quarantine.
select
    trip_type,
    data_month,
    quarantine_reason,
    {%- for column in tlc_columns() %}
    {{ column.name }},
    {%- endfor %}
    _run_id,
    _source_uri,
    _etag,
    _loaded_at
from {{ ref('slv_tlc_trips_checked') }}
where quarantine_reason is not null
