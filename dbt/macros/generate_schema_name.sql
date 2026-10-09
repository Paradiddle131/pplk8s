-- Use the custom schema verbatim (bronze, silver, gold, exposed) instead of <target schema>_<custom>.
-- The target schema (default `public`) only applies to models without a +schema config.
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
