-- Generic test, the bronze -> silver hop (semantic/PLAN.md SL-9): silver holds exactly bronze's latest
-- load of each key (greatest _loaded_at, then greatest `tie_breaker`), so the two agree on rows and,
-- given `amount`, on its sum. The latest load is found by joins on maxima rather than silver's
-- row_number, so the test re-derives silver instead of repeating it.
{% test latest_load_reconciles(model, bronze, keys, tie_breaker, amount=none) %}

{%- set measures = ['row_count'] + ([amount] if amount else []) %}
{%- set on_keys %}{% for key in keys %}b.{{ key }} = l.{{ key }} and {% endfor %}{% endset %}

{%- set upstream %}
    with last_load as (
        select {{ keys | join(', ') }}, max(_loaded_at) as _loaded_at
        from {{ bronze }}
        group by {{ keys | join(', ') }}
    ),

    last_row as (
        select {% for key in keys %}b.{{ key }}, {% endfor %}b._loaded_at, max(b.{{ tie_breaker }}) as {{ tie_breaker }}
        from {{ bronze }} as b
        inner join last_load as l on {{ on_keys }}b._loaded_at = l._loaded_at
        group by {% for key in keys %}b.{{ key }}, {% endfor %}b._loaded_at
    )

    select count(*) as row_count{{ ', sum(b.' ~ amount ~ ') as ' ~ amount if amount }}
    from {{ bronze }} as b
    inner join last_row as l
        on {{ on_keys }}b._loaded_at = l._loaded_at and b.{{ tie_breaker }} = l.{{ tie_breaker }}
{%- endset %}

{%- set downstream %}
    select count(*) as row_count{{ ', sum(' ~ amount ~ ') as ' ~ amount if amount }}
    from {{ model }}
{%- endset %}

{{ hop_mismatches('bronze -> silver ' ~ model.identifier, upstream, downstream, [], measures) }}

{% endtest %}
