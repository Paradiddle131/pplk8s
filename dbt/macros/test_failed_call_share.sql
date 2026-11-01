-- Generic test (semantic/PLAN.md SL-18): per prompt version, the share of rows whose model call failed
-- (a non-empty `column_name`, AI.GENERATE's status) stays at or below max_share; the dbt counterpart of
-- AI functions' max_error_ratio. Returns one row per prompt version above it.
{% test failed_call_share(model, column_name, max_share) %}

select prompt_version, failed_calls, calls
from (
    select
        prompt_version,
        sum(case when {{ column_name }} <> '' then 1 else 0 end) as failed_calls,
        count(*) as calls
    from {{ model }}
    group by prompt_version
) as versions
where failed_calls > {{ max_share }} * calls

{% endtest %}
