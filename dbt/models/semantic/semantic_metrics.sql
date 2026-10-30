{{ config(alias='metrics', tags=['sales']) }}

-- One row per metric of the semantic layer (semantic/PLAN.md SL-3), rendered from dbt's graph at build time,
-- so the table always holds the words of the YAML this build parsed, never a hand-kept copy.
-- Tagged sales like the time spine; which DAG builds the semantic stage is S4's call (#103).
-- pipelines: the owning tags of the models under the metric's semantic models, the tag whose readiness
-- says how fresh the metric is (SL-4).
{%- set layer_tags = ['bronze', 'silver', 'gold', 'exposed', 'semantic'] %}
{%- set rows = [] %}
{%- if execute %}
  {%- for metric in graph.metrics.values() | sort(attribute='name') %}
    {%- set models = [] %}
    {%- set pipelines = [] %}
    {%- for model_id in semantic_models_of_metric(metric.unique_id) %}
      {%- set semantic_model = graph.semantic_models[model_id] %}
      {%- do models.append(semantic_model.name) %}
      {%- for node_id in semantic_model.depends_on.nodes %}
        {%- for tag in graph.nodes[node_id].tags if tag not in layer_tags and tag not in pipelines %}
          {%- do pipelines.append(tag) %}
        {%- endfor %}
      {%- endfor %}
    {%- endfor %}
    {%- do rows.append({
      'metric_name': metric.name,
      'label': metric.label,
      'description': metric.description,
      'metric_type': metric.type,
      'semantic_models': models | join(','),
      'pipelines': pipelines | sort | join(','),
    }) %}
  {%- endfor %}
{%- endif %}
{%- set columns = ['metric_name', 'label', 'description', 'metric_type', 'semantic_models', 'pipelines'] %}

{% for row in rows %}
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
