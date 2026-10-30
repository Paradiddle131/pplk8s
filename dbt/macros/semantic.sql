-- The semantic models a metric reads, as graph unique ids (semantic/PLAN.md SL-3, SL-4): a simple
-- metric depends on its semantic model, any other metric on the metrics it combines.
{% macro semantic_models_of_metric(node_id) -%}
    {%- if node_id.startswith('semantic_model.') -%}
        {{ return([node_id]) }}
    {%- endif -%}
    {%- set found = [] -%}
    {%- for parent in graph.metrics[node_id].depends_on.nodes -%}
        {%- for model in semantic_models_of_metric(parent) if model not in found -%}
            {%- do found.append(model) -%}
        {%- endfor -%}
    {%- endfor -%}
    {{ return(found | sort) }}
{%- endmacro %}
