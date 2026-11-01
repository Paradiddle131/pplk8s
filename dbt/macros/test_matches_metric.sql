-- Generic test, the metric -> gold hop (semantic/PLAN.md SL-9): a hand-written column equals the metric
-- of the same meaning, per day. The metric is rendered from dbt's graph, as the YAML defines it: its
-- aggregation over its semantic model's relation, its filters, and its agg_time_dimension as the day, so
-- a metric whose YAML drifts from the hand-written SQL fails the build. MetricFlow itself does not run in
-- dbt build; tests/e2e/semantic-check.sh compares its own queries.
-- A filter may name dimensions of the metric's own semantic model only. The relation is named, not
-- ref'd, so the test depends on the column's model alone and runs with that model's stage.
-- A cumulative metric with a window of days over a simple metric renders as that simple metric over
-- the window ending on each of the model's days (the day and the window's count - 1 days before), as
-- MetricFlow joins it to the time spine; the model's days are the days compared.
-- A conversion rate with a window of days renders as MetricFlow 0.15 computes it: base rows and
-- conversion rows join on the entity where the base's day is on or before the conversion's and fewer
-- than the window's count of days before it; each conversion row (its semantic model's primary key)
-- counts once, on the latest base day it joined; the rate is the conversion metric over those rows
-- divided by the base metric, per base day. The model's column holds that rate, one row per day.

-- A simple metric's parts, from dbt's graph: its semantic model's relation, its time column, the
-- aggregation of an expression, its expression, and its filters as SQL (plus `extra_filters`, a
-- metric input's own filter), all over unqualified column names.
{% macro matches_metric_simple(metric, extra_filters=[]) %}
    {%- set found = graph.metrics.values() | selectattr('name', 'equalto', metric) | list %}
    {%- if found | length != 1 or found[0].type != 'simple' %}
        {{ exceptions.raise_compiler_error("matches_metric: no simple metric named " ~ metric) }}
    {%- endif %}
    {%- set params = found[0].type_params.metric_aggregation_params %}
    {%- set semantic_model = graph.semantic_models.values() | selectattr('name', 'equalto', params.semantic_model) | first %}
    {%- set entities = {} %}
    {%- for entity in semantic_model.entities %}
        {%- do entities.update({entity.name: entity.expr or entity.name}) %}
    {%- endfor %}
    {%- set columns = {} %}
    {%- for dimension in semantic_model.dimensions %}
        {%- do columns.update({dimension.name: dimension.expr or dimension.name}) %}
    {%- endfor %}

    {%- set conditions = [] %}
    {%- for where in (found[0].filter.where_filters if found[0].filter else []) + extra_filters %}
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
    {%- if agg not in ['sum', 'count', 'count_distinct'] %}
        {{ exceptions.raise_compiler_error("matches_metric: " ~ metric ~ " aggregates with " ~ agg ~ ", which the test does not render") }}
    {%- endif %}
    {%- set primary = semantic_model.entities | selectattr('type', 'equalto', 'primary') | list %}
    {%- do return({
        'relation': semantic_model.node_relation.relation_name,
        'semantic_model': semantic_model.name,
        'time': columns[params.agg_time_dimension],
        'agg': agg,
        'expr': expr,
        'entities': entities,
        'primary': (primary[0].expr or primary[0].name) if primary else none,
        'conditions': conditions,
    }) %}
{% endmacro %}

{% macro matches_metric_aggregate(agg, expr) %}
    {%- do return({'sum': 'sum(' ~ expr ~ ')', 'count': 'count(' ~ expr ~ ')', 'count_distinct': 'count(distinct ' ~ expr ~ ')'}[agg]) %}
{% endmacro %}

{% test matches_metric(model, column_name, metric, time_column) %}

{%- if execute %}
    {%- set found = graph.metrics.values() | selectattr('name', 'equalto', metric) | list %}
    {%- if found | length != 1 or found[0].type not in ['simple', 'cumulative', 'conversion'] %}
        {{ exceptions.raise_compiler_error("matches_metric: no simple, cumulative or conversion metric named " ~ metric) }}
    {%- endif %}
    {%- set tolerance = 0 %}

    {%- if found[0].type == 'conversion' %}
        {%- set conversion = found[0].type_params.conversion_type_params %}
        {%- if conversion.calculation != 'conversion_rate' or not conversion.window or conversion.window.granularity != 'day'
              or conversion.constant_properties or not conversion.base_metric or not conversion.conversion_metric or found[0].filter %}
            {{ exceptions.raise_compiler_error("matches_metric: " ~ metric ~ " is a conversion other than a rate over a window of days between two metrics") }}
        {%- endif %}
        {%- set base = matches_metric_simple(conversion.base_metric.name, conversion.base_metric.filter.where_filters if conversion.base_metric.filter else []) %}
        {%- set converted = matches_metric_simple(conversion.conversion_metric.name, conversion.conversion_metric.filter.where_filters if conversion.conversion_metric.filter else []) %}
        {%- if conversion.entity not in base.entities or conversion.entity not in converted.entities or not converted.primary %}
            {{ exceptions.raise_compiler_error("matches_metric: " ~ metric ~ "'s entity " ~ conversion.entity ~ " is not on both semantic models, or " ~ converted.semantic_model ~ " has no primary key") }}
        {%- endif %}
        {%- set tolerance = 0.000001 %}
        {%- set upstream %}
        with base_rows as (
            select {{ base.time }} as day, {{ base.entities[conversion.entity] }} as entity_key, {{ base.expr }} as base_value
            from {{ base.relation }}
            {%- if base.conditions %}
            where {{ base.conditions | join(' and ') }}
            {%- endif %}
        ),

        conversion_rows as (
            select {{ converted.time }} as day, {{ converted.entities[conversion.entity] }} as entity_key,
                   {{ converted.primary }} as conversion_key, {{ converted.expr }} as conversion_value
            from {{ converted.relation }}
            {%- if converted.conditions %}
            where {{ converted.conditions | join(' and ') }}
            {%- endif %}
        ),

        attributed as (
            select distinct
                c.conversion_key,
                c.conversion_value,
                first_value(b.day) over (partition by c.conversion_key order by b.day desc) as day
            from base_rows as b
            inner join conversion_rows as c
                on c.entity_key = b.entity_key
                and b.day <= c.day
                and b.day > {{ days_before('c.day', conversion.window.count) }}
        ),

        base_days as (
            select day, {{ matches_metric_aggregate(base.agg, 'base_value') }} as base_value
            from base_rows
            group by day
        ),

        conversion_days as (
            select day, {{ matches_metric_aggregate(converted.agg, 'conversion_value') }} as conversion_value
            from attributed
            group by day
        )

        select b.day, cast(coalesce(c.conversion_value, 0) as {{ dbt.type_numeric() }}) / nullif(b.base_value, 0) as {{ column_name }}
        from base_days as b
        left join conversion_days as c on c.day = b.day
        {%- endset %}
    {%- else %}
        {%- set window = none %}
        {%- set simple = metric %}
        {%- if found[0].type == 'cumulative' %}
            {%- set cumulative = found[0].type_params.cumulative_type_params %}
            {%- if not cumulative.window or cumulative.window.granularity != 'day' or cumulative.grain_to_date or cumulative.metric.filter %}
                {{ exceptions.raise_compiler_error("matches_metric: " ~ metric ~ " is cumulative over something other than a window of days on a simple metric") }}
            {%- endif %}
            {%- set window = cumulative.window.count %}
            {%- set simple = cumulative.metric.name %}
        {%- endif %}
        {%- set parts = matches_metric_simple(simple) %}
        {%- set aggregate = matches_metric_aggregate(parts.agg, parts.expr) %}
        {%- set upstream %}
            {%- if window %}
            select model_days.day, {{ aggregate }} as {{ column_name }}
            from (select distinct {{ time_column }} as day from {{ model }}) as model_days
            inner join {{ parts.relation }}
                on {{ parts.time }} <= model_days.day and {{ parts.time }} > {{ days_before('model_days.day', window) }}
            {%- if parts.conditions %}
            where {{ parts.conditions | join(' and ') }}
            {%- endif %}
            group by model_days.day
            {%- else %}
            select {{ parts.time }} as day, {{ aggregate }} as {{ column_name }}
            from {{ parts.relation }}
            {%- if parts.conditions %}
            where {{ parts.conditions | join(' and ') }}
            {%- endif %}
            group by {{ parts.time }}
            {%- endif %}
        {%- endset %}
    {%- endif %}

    {%- set downstream %}
        select {{ time_column }} as day, sum({{ column_name }}) as {{ column_name }}
        from {{ model }}
        group by {{ time_column }}
    {%- endset %}

{{ hop_mismatches('metric ' ~ metric ~ ' -> ' ~ model.identifier ~ '.' ~ column_name, upstream, downstream, ['day'], [column_name], tolerance) }}
{%- else %}
select 1 as placeholder where 1 = 0
{%- endif %}

{% endtest %}
