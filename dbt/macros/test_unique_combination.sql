-- Generic test: the listed columns together are unique and not null.
-- Stands in for dbt_utils.unique_combination_of_columns so the project needs no packages.
{% test unique_combination(model, columns) %}

select
    {{ columns | join(', ') }},
    count(*) as row_count
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1

{% endtest %}
