{{ config(tags=['gold']) }}

-- Gold revenue must equal the silver sum of non-cancelled order amounts.
-- Returns a row (and so fails) only when the two totals differ.
-- Lives in tests/gold/ and is tagged gold: it needs gold and silver built, so it runs with the gold stage only.
with gold_total as (
    select coalesce(sum(revenue_eur), 0) as total
    from {{ ref('gld_daily_sales') }}
),

silver_total as (
    select coalesce(sum(amount), 0) as total
    from {{ ref('slv_orders') }}
    where status <> 'cancelled'
)

select
    gold_total.total as gold_total,
    silver_total.total as silver_total
from gold_total
cross join silver_total
where gold_total.total <> silver_total.total
