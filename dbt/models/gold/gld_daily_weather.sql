{{ config(alias='daily_weather', tags=['sales']) }}

select
    location,
    {{ utc_date('observed_at') }} as date,
    round(avg(temperature_c), 2) as avg_temperature_c,
    min(temperature_c) as min_temperature_c,
    max(temperature_c) as max_temperature_c,
    sum(precipitation_mm) as total_precipitation_mm
from {{ ref('slv_hourly_weather') }}
group by location, {{ utc_date('observed_at') }}
