-- The migration rehearsal's parity (semantic/PLAN.md SL-11): one consumer's legacy relation against
-- its new model, compared with the layer hops' own comparison (hop_mismatches, SL-9).
-- `keys` and `fields` map the consumer's column names, as the legacy relation spells them, to the new
-- model's columns, so the report speaks the consumer's words. Returns one row per field, plus
-- `row_count` (a key on one side only, or twice on one side), with the keys compared on either side
-- and how many of them differ by more than `tolerance`.
{% macro parity_rows(consumer, legacy, new, keys, fields, tolerance=0) -%}
{%- set key_names = keys.keys() | list %}
{%- set legacy_side %}
    select {% for key in keys %}{{ key }}, {% endfor %}1 as row_count{% for field in fields %}, {{ field }}{% endfor %}
    from {{ legacy }}
{%- endset %}
{%- set new_side %}
    select {% for key, column in keys.items() %}{{ column }} as {{ key }}, {% endfor %}1 as row_count{% for field, column in fields.items() %}, {{ column }} as {{ field }}{% endfor %}
    from {{ new }}
{%- endset %}
{%- set string = dbt.type_string() %}
{%- for field in ['row_count'] + (fields.keys() | list) %}
select
    cast('{{ consumer }}' as {{ string }}) as consumer,
    cast('{{ field }}' as {{ string }}) as field,
    cast('{{ legacy.schema }}.{{ legacy.identifier }}' as {{ string }}) as legacy_relation,
    cast('{{ new.schema }}.{{ new.identifier }}' as {{ string }}) as new_relation,
    (
        select count(*) from (
            select {{ key_names | join(', ') }} from ({{ legacy_side }}) as l
            union distinct
            select {{ key_names | join(', ') }} from ({{ new_side }}) as n
        ) as compared_keys
    ) as keys_compared,
    (
        select count(*) from (
            {{ hop_mismatches(consumer ~ ' ' ~ field, legacy_side, new_side, key_names, [field], tolerance) }}
        ) as differing_keys
    ) as keys_differing
{{ 'union all' if not loop.last }}
{% endfor %}
{%- endmacro %}
