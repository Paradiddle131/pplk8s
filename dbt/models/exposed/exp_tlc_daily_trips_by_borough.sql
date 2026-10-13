{{ config(alias='tlc_daily_trips_by_borough', tags=['tlc']) }}

-- Daily trips and revenue per pickup borough; a view over tlc models only (D20, issue #27).
-- Pickup zones missing from the zone seed count as borough 'Unknown', as the seed's own id 264 does.
select
    g.pickup_date,
    g.data_month,
    g.trip_type,
    coalesce(z.borough, 'Unknown') as borough,
    sum(g.trips) as trips,
    sum(g.passengers) as passengers,
    sum(g.total_amount_usd) as total_amount_usd
from {{ ref('gld_tlc_daily_trips') }} as g
left join {{ ref('tlc_taxi_zones') }} as z
    on z.location_id = g.pickup_location_id
group by g.pickup_date, g.data_month, g.trip_type, coalesce(z.borough, 'Unknown')
