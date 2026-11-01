{{ config(tags=['tlc', 'silver']) }}

-- Per built month, the latest completed file version's bronze rows = silver + quarantine rows
-- (Phase 8 exit); a mismatch means a month was lost, duplicated, or left stale by a rebuild.
with versions as (
    select
        source_uri,
        etag,
        row_number() over (partition by source_uri order by completed_at desc) as version_rank
    from {{ source('ops', 'file_versions') }}
    {{ tlc_month_filter(tlc_month_of('source_uri')) }}
),

bronze as (
    select b.data_month, count(*) as row_count
    from (
        select data_month, _source_uri, _etag from {{ ref('brz_tlc_yellow_trips') }}
        union all
        select data_month, _source_uri, _etag from {{ ref('brz_tlc_green_trips') }}
    ) as b
    inner join versions as v
        on v.source_uri = b._source_uri and v.etag = b._etag and v.version_rank = 1
    group by b.data_month
),

built as (
    select data_month, count(*) as row_count from {{ ref('slv_tlc_trips') }} group by data_month
    union all
    select data_month, count(*) as row_count from {{ ref('slv_tlc_trips_quarantine') }} group by data_month
),

layered as (
    select data_month, sum(row_count) as row_count from built group by data_month
)

select
    coalesce(bronze.data_month, layered.data_month) as data_month,
    bronze.row_count as bronze_rows,
    layered.row_count as silver_plus_quarantine_rows
from bronze
full outer join layered on layered.data_month = bronze.data_month
where coalesce(bronze.row_count, -1) <> coalesce(layered.row_count, -1)
{%- if tlc_data_month() is not none %}
    and coalesce(bronze.data_month, layered.data_month) = '{{ tlc_data_month() }}'
{%- endif %}
