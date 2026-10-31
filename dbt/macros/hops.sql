-- Layer reconciliation (semantic/PLAN.md SL-9): one comparison every hop test shares.
-- `upstream` and `downstream` are SELECTs that each return the `keys` and `measures` columns; a key
-- missing on one side counts as 0 there. Returns one row per key whose measures differ by more than
-- `tolerance`, led by the hop's name, so a failing build says which hand-off lost or doubled data.
-- Both sides are stacked and summed rather than full-joined: BigQuery's FULL JOIN needs an equality
-- condition, which an all-totals hop (no keys) lacks.
{% macro hop_mismatches(hop, upstream, downstream, keys, measures, tolerance=0) -%}
{%- set numeric = dbt.type_numeric() %}
with upstream as (
    {{ upstream }}
),

downstream as (
    {{ downstream }}
),

stacked as (
    select
        {%- for key in keys %}
        {{ key }},
        {%- endfor %}
        {%- for measure in measures %}
        cast(coalesce({{ measure }}, 0) as {{ numeric }}) as upstream_{{ measure }},
        cast(0 as {{ numeric }}) as downstream_{{ measure }}{{ ',' if not loop.last }}
        {%- endfor %}
    from upstream
    union all
    select
        {%- for key in keys %}
        {{ key }},
        {%- endfor %}
        {%- for measure in measures %}
        cast(0 as {{ numeric }}) as upstream_{{ measure }},
        cast(coalesce({{ measure }}, 0) as {{ numeric }}) as downstream_{{ measure }}{{ ',' if not loop.last }}
        {%- endfor %}
    from downstream
),

compared as (
    select
        '{{ hop }}' as hop,
        {%- for key in keys %}
        {{ key }},
        {%- endfor %}
        {%- for measure in measures %}
        sum(upstream_{{ measure }}) as upstream_{{ measure }},
        sum(downstream_{{ measure }}) as downstream_{{ measure }}{{ ',' if not loop.last }}
        {%- endfor %}
    from stacked
    {%- if keys %}
    group by {{ keys | join(', ') }}
    {%- endif %}
)

select *
from compared
where
    {%- for measure in measures %}
    abs(upstream_{{ measure }} - downstream_{{ measure }}) > {{ tolerance }}{{ ' or' if not loop.last }}
    {%- endfor %}
{%- endmacro %}
