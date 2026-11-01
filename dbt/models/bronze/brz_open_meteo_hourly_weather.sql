{{ config(alias='open_meteo_hourly_weather', tags=['sales']) }}

select
    cast(location as {{ dbt.type_string() }}) as location,
    {{ cast_decimal("latitude", 8, 4) }} as latitude,
    {{ cast_decimal("longitude", 8, 4) }} as longitude,
    cast(observed_at as {{ type_timestamptz() }}) as observed_at,
    {{ cast_decimal("temperature_c", 5, 2) }} as temperature_c,
    {{ cast_decimal("precipitation_mm", 6, 2) }} as precipitation_mm,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'open_meteo_hourly_weather') }}
