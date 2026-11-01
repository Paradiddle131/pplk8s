{{ config(tags=['exposed', 'tlc']) }}

-- Per pickup day and trip type, the boroughs add up to gold's zones: the zone join drops or doubles
-- no trip. Amounts are floats summed in a different order, so they agree to the cent.
{% set upstream %}
    select pickup_date, trip_type, sum(trips) as trips, sum(passengers) as passengers,
           sum(total_amount_usd) as total_amount_usd
    from {{ ref('gld_tlc_daily_trips') }}
    group by pickup_date, trip_type
{% endset %}

{% set downstream %}
    select pickup_date, trip_type, trips, passengers, total_amount_usd
    from {{ ref('exp_tlc_daily_trips_by_borough') }}
{% endset %}

{{ hop_mismatches('gold -> exposed tlc_daily_trips_by_borough', upstream, downstream, ['pickup_date', 'trip_type'],
                  ['trips', 'passengers', 'total_amount_usd'], tolerance=0.01) }}
