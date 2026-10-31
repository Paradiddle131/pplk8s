{{ config(alias='glossary', tags=['sales']) }}

-- One row per glossary term: a business term that is not a metric, from `config.meta.glossary` on the model
-- that holds it (semantic/PLAN.md SL-3), rendered from dbt's graph at build time like semantic.metrics.
-- Tagged sales with semantic.metrics; check_catalog.py checks the terms against the metrics and dimensions.
{%- set rows = [] %}
{%- if execute %}
  {%- for node in graph.nodes.values() if node.resource_type == 'model' %}
    {%- for entry in node.config.meta.get('glossary', []) %}
      {%- do rows.append({
        'term': entry.term,
        'description': entry.description | trim,
        'synonyms': entry.get('synonyms', []) | join(','),
        'metrics': entry.get('metrics', []) | join(','),
        'dimensions': entry.get('dimensions', []) | join(','),
        'model_name': node.name,
      }) %}
    {%- endfor %}
  {%- endfor %}
{%- endif %}
{%- set columns = ['term', 'description', 'synonyms', 'metrics', 'dimensions', 'model_name'] %}

{% for row in rows | sort(attribute='term') %}
select
  {%- for column in columns %}
    cast('{{ dbt.escape_single_quotes(row[column]) }}' as {{ dbt.type_string() }}) as {{ column }}{{ ',' if not loop.last }}
  {%- endfor %}
{{ 'union all' if not loop.last }}
{% else %}
select
  {%- for column in columns %}
    cast(null as {{ dbt.type_string() }}) as {{ column }}{{ ',' if not loop.last }}
  {%- endfor %}
where 1 = 0
{% endfor %}
