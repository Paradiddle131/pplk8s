{{ config(alias='open_meteo_hourly_weather') }}

select
    cast(location as text) as location,
    cast(latitude as numeric(8,4)) as latitude,
    cast(longitude as numeric(8,4)) as longitude,
    cast(observed_at as timestamptz) as observed_at,
    cast(temperature_c as numeric(5,2)) as temperature_c,
    cast(precipitation_mm as numeric(6,2)) as precipitation_mm,
    _run_id,
    _interval_start,
    _interval_end,
    _page,
    _source_uri,
    _loaded_at
from {{ source('ds_source', 'open_meteo_hourly_weather') }}
