{{ config(tags=['tlc', 'gold']) }}

-- Per month and trip type, gold's trip count equals silver's row count.
with silver as (
    select data_month, trip_type, count(*) as trips from {{ ref('slv_tlc_trips') }} group by data_month, trip_type
),

gold as (
    select data_month, trip_type, sum(trips) as trips from {{ ref('gld_tlc_daily_trips') }} group by data_month, trip_type
)

select
    coalesce(silver.data_month, gold.data_month) as data_month,
    coalesce(silver.trip_type, gold.trip_type) as trip_type,
    silver.trips as silver_trips,
    gold.trips as gold_trips
from silver
full outer join gold
    on gold.data_month = silver.data_month and gold.trip_type = silver.trip_type
where coalesce(silver.trips, -1) <> coalesce(gold.trips, -1)
