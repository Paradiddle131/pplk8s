{{ config(materialized='ephemeral', tags=['tlc']) }}

-- Yellow and green rows of the latest completed file version of each month (ops.file_versions),
-- each with its first broken quarantine rule (D36), or NULL when the row is clean.
-- A version still loading has no file_versions row, so its chunks stay invisible.
with versions as (
    select
        source_uri,
        etag,
        row_number() over (partition by source_uri order by completed_at desc) as version_rank
    from {{ source('ops', 'file_versions') }}
    {{ tlc_month_filter(tlc_month_of('source_uri')) }}
),

landed as (
    select * from {{ ref('brz_tlc_yellow_trips') }}
    union all
    select * from {{ ref('brz_tlc_green_trips') }}
),

current_version as (
    select
        landed.*,
        cast(landed.data_month || '-01' as timestamp) as month_start
    from landed
    inner join versions
        on versions.source_uri = landed._source_uri
        and versions.etag = landed._etag
        and versions.version_rank = 1
    {{ tlc_month_filter('landed.data_month') }}
)

select
    *,
    case
        when fare_amount < 0 or total_amount < 0 then 'negative_amount'
        when pickup_at is null
            or pickup_at < month_start
            or pickup_at >= {{ dbt.dateadd('month', 1, 'month_start') }} then 'pickup_outside_month'
        when dropoff_at < pickup_at then 'dropoff_before_pickup'
        when dropoff_at > {{ dbt.dateadd('hour', 24, 'pickup_at') }} then 'over_24_hours'
    end as quarantine_reason
from current_version
