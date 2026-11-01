-- Generic test, the metric -> gold hop (semantic/PLAN.md SL-9): a hand-written column equals the simple
-- metric of the same meaning, per day. The metric is rendered from dbt's graph, as the YAML defines it:
-- its aggregation over its semantic model's relation, its filters, and its agg_time_dimension as the
-- day, so a metric whose YAML drifts from the hand-written SQL fails the build. MetricFlow itself does
-- not run in dbt build; tests/e2e/semantic-check.sh compares its own queries.
-- A filter may name dimensions of the metric's own semantic model only. The relation is named, not
-- ref'd, so the test depends on the column's model alone and runs with that model's stage.
-- A cumulative metric with a window of days over a simple metric renders as that simple metric over
-- the window ending on each of the model's days (the day and the window's count - 1 days before), as
-- MetricFlow joins it to the time spine; the model's days are the days compared.
{% test matches_metric(model, column_name, metric, time_column) %}

{%- if execute %}
    {%- set found = graph.metrics.values() | selectattr('name', 'equalto', metric) | list %}
    {%- set window = none %}
    {%- if found | length == 1 and found[0].type == 'cumulative' %}
        {%- set cumulative = found[0].type_params.cumulative_type_params %}
        {%- if not cumulative.window or cumulative.window.granularity != 'day' or cumulative.grain_to_date or cumulative.metric.filter %}
            {{ exceptions.raise_compiler_error("matches_metric: " ~ metric ~ " is cumulative over something other than a window of days on a simple metric") }}
        {%- endif %}
        {%- set window = cumulative.window.count %}
        {%- set found = graph.metrics.values() | selectattr('name', 'equalto', cumulative.metric.name) | list %}
    {%- endif %}
    {%- if found | length != 1 or found[0].type != 'simple' %}
        {{ exceptions.raise_compiler_error("matches_metric: no simple or cumulative metric named " ~ metric) }}
    {%- endif %}
    {%- set params = found[0].type_params.metric_aggregation_params %}
    {%- set semantic_model = graph.semantic_models.values() | selectattr('name', 'equalto', params.semantic_model) | first %}
    {%- set entities = semantic_model.entities | map(attribute='name') | list %}
    {%- set columns = {} %}
    {%- for dimension in semantic_model.dimensions %}
        {%- do columns.update({dimension.name: dimension.expr or dimension.name}) %}
    {%- endfor %}

    {%- set conditions = [] %}
    {%- for where in (found[0].filter.where_filters if found[0].filter else []) %}
        {%- set ns = namespace(sql=where.where_sql_template) %}
        {%- for entity, name in modules.re.findall("Dimension\(\s*'(\w+?)__(\w+)'\s*\)", ns.sql) %}
            {%- if entity not in entities or name not in columns %}
                {{ exceptions.raise_compiler_error("matches_metric: " ~ metric ~ " filters on " ~ entity ~ "__" ~ name ~ ", not a dimension of " ~ semantic_model.name) }}
            {%- endif %}
        {%- endfor %}
        {%- do conditions.append(modules.re.sub("\{\{\s*Dimension\(\s*'\w+?__(\w+)'\s*\)\s*\}\}", "\\1", ns.sql)) %}
    {%- endfor %}

    {%- set agg = params.agg %}
    {%- set expr = found[0].type_params.expr %}
    {%- set aggregate = {'sum': 'sum(' ~ expr ~ ')', 'count': 'count(' ~ expr ~ ')', 'count_distinct': 'count(distinct ' ~ expr ~ ')'}.get(agg) %}
    {%- if not aggregate %}
        {{ exceptions.raise_compiler_error("matches_metric: " ~ metric ~ " aggregates with " ~ agg ~ ", which the test does not render") }}
    {%- endif %}

    {%- set time = columns[params.agg_time_dimension] %}
    {%- set upstream %}
        {%- if window %}
        select model_days.day, {{ aggregate }} as {{ column_name }}
        from (select distinct {{ time_column }} as day from {{ model }}) as model_days
        inner join {{ semantic_model.node_relation.relation_name }}
            on {{ time }} <= model_days.day and {{ time }} > {{ days_before('model_days.day', window) }}
        {%- if conditions %}
        where {{ conditions | join(' and ') }}
        {%- endif %}
        group by model_days.day
        {%- else %}
        select {{ time }} as day, {{ aggregate }} as {{ column_name }}
        from {{ semantic_model.node_relation.relation_name }}
        {%- if conditions %}
        where {{ conditions | join(' and ') }}
        {%- endif %}
        group by {{ time }}
        {%- endif %}
    {%- endset %}

    {%- set downstream %}
        select {{ time_column }} as day, sum({{ column_name }}) as {{ column_name }}
        from {{ model }}
        group by {{ time_column }}
    {%- endset %}

{{ hop_mismatches('metric ' ~ metric ~ ' -> ' ~ model.identifier ~ '.' ~ column_name, upstream, downstream, ['day'], [column_name]) }}
{%- else %}
select 1 as placeholder where 1 = 0
{%- endif %}

{% endtest %}
