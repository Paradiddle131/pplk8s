{{ config(alias='hourly_weather') }}

-- Latest row per (location, observed_at): greatest _loaded_at, then greatest _run_id as tie-breaker.
with ranked as (
    select
        *,
        row_number() over (
            partition by location, observed_at
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_open_meteo_hourly_weather') }}
)

select
    location,
    latitude,
    longitude,
    observed_at,
    temperature_c,
    precipitation_mm,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
