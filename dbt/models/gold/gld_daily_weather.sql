{{ config(alias='daily_weather') }}

-- dialect: the UTC day is cast(observed_at at time zone 'UTC' as date) in Postgres; BigQuery uses DATE(observed_at, 'UTC').
select
    location,
    cast(observed_at at time zone 'UTC' as date) as date,
    round(avg(temperature_c), 2) as avg_temperature_c,
    min(temperature_c) as min_temperature_c,
    max(temperature_c) as max_temperature_c,
    sum(precipitation_mm) as total_precipitation_mm
from {{ ref('slv_hourly_weather') }}
group by location, cast(observed_at at time zone 'UTC' as date)
