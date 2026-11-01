{{ config(
    alias='customer_actions',
    tags=['customer_actions'],
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='event_id',
    on_schema_change='append_new_columns',
    partition_by={'field': 'event_date', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['customer_id'],
) }}

-- One row per action, latest load wins, built incrementally (semantic/PLAN.md SL-15): a build reads only
-- what bronze landed since the newest load already here, minus a lookback, and merges it on event_id.
-- Reading by arrival rather than by event date is what lets a late event in: an action received a day
-- after its event_ts lands in that later load and merges into its own, older event_date. The lookback
-- (var customer_actions_lookback_hours) re-reads loads that committed after a newer one had already
-- been merged; re-reading is harmless, since a merge on event_id replaces the row with the same values.
-- BigQuery partitions by event_date and clusters by customer_id; Postgres ignores both.
with landed as (
    select *
    from {{ ref('brz_synthetic_customer_actions') }}
    {%- if is_incremental() %}
    where _loaded_at > (
        select {{ hours_before('max(_loaded_at)', var('customer_actions_lookback_hours')) }} from {{ this }}
    )
    {%- endif %}
),

ranked as (
    select
        *,
        row_number() over (
            partition by event_id
            order by _loaded_at desc, _run_id desc
        ) as row_rank
    from landed
)

select
    event_id,
    customer_id,
    session_id,
    action_type,
    channel,
    event_ts,
    {{ utc_date('event_ts') }} as event_date,
    received_ts,
    _run_id,
    _loaded_at
from ranked
where row_rank = 1
