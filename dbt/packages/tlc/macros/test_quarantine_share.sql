-- Generic test: per data_month, the share of quarantined rows (model) among all rows
-- (model + clean) stays at or below max_share. Returns one row per month above it.
{% test quarantine_share(model, clean, max_share) %}

with quarantined as (
    select data_month, count(*) as row_count from {{ model }} group by data_month
),

kept as (
    select data_month, count(*) as row_count from {{ clean }} group by data_month
),

months as (
    select
        coalesce(kept.data_month, quarantined.data_month) as data_month,
        coalesce(quarantined.row_count, 0) as quarantined_rows,
        coalesce(quarantined.row_count, 0) + coalesce(kept.row_count, 0) as total_rows
    from kept
    full outer join quarantined on quarantined.data_month = kept.data_month
)

select data_month, quarantined_rows, total_rows
from months
where quarantined_rows > {{ max_share }} * total_rows

{% endtest %}
