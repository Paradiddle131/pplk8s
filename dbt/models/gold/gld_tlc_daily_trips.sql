{{ config(
    alias='tlc_daily_trips',
    tags=['tlc'],
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='data_month',
    on_schema_change='append_new_columns',
) }}

-- Trips per pickup day, trip type and pickup zone, one data month replaced per build (D36).
-- Amounts are in USD; trip_distance in miles.
select
    data_month,
    trip_type,
    cast(pickup_at as date) as pickup_date,
    pickup_location_id,
    count(*) as trips,
    sum(passenger_count) as passengers,
    sum(trip_distance) as trip_distance_mi,
    sum(fare_amount) as fare_amount_usd,
    sum(tip_amount) as tip_amount_usd,
    sum(total_amount) as total_amount_usd
from {{ ref('slv_tlc_trips') }}
{{ tlc_month_filter() }}
group by data_month, trip_type, cast(pickup_at as date), pickup_location_id
