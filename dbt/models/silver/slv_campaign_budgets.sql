{{ config(alias='campaign_budgets', tags=['marketing']) }}

-- Latest row per snapshot_date, campaign_id: greatest _loaded_at, then greatest _run_id as tie-breaker.
-- A balance (what is left of the month's budget after the day's spend): one snapshot per campaign per
-- day, never summed across days (remaining_budget_eur takes the last day's, semantic/PLAN.md SL-8).
with ranked as (
    select
        *,
        row_number() over (
            partition by snapshot_date, campaign_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from {{ ref('brz_synthetic_campaign_budgets') }}
)

select
    snapshot_date,
    campaign_id,
    budget_eur,
    remaining_eur,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
