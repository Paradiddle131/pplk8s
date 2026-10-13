-- NYC TLC trip models (PLAN.md D34-D36): the canonical columns, the bronze select, and the month var.

-- Canonical trip columns in output order: name, type, and the landed column per trip type
-- (EL Factory lower-cases every published name; none = the trip type never publishes it).
-- dialect: `double precision` and `timestamp` are FLOAT64 and DATETIME on BigQuery; TLC timestamps are NYC local time.
{% macro tlc_columns() %}
    {{ return([
        {'name': 'vendor_id', 'type': 'integer', 'yellow': 'vendorid', 'green': 'vendorid'},
        {'name': 'pickup_at', 'type': 'timestamp', 'yellow': 'tpep_pickup_datetime', 'green': 'lpep_pickup_datetime'},
        {'name': 'dropoff_at', 'type': 'timestamp', 'yellow': 'tpep_dropoff_datetime', 'green': 'lpep_dropoff_datetime'},
        {'name': 'passenger_count', 'type': 'bigint', 'yellow': 'passenger_count', 'green': 'passenger_count'},
        {'name': 'trip_distance', 'type': 'double precision', 'yellow': 'trip_distance', 'green': 'trip_distance'},
        {'name': 'rate_code_id', 'type': 'bigint', 'yellow': 'ratecodeid', 'green': 'ratecodeid'},
        {'name': 'store_and_fwd_flag', 'type': 'text', 'yellow': 'store_and_fwd_flag', 'green': 'store_and_fwd_flag'},
        {'name': 'pickup_location_id', 'type': 'integer', 'yellow': 'pulocationid', 'green': 'pulocationid'},
        {'name': 'dropoff_location_id', 'type': 'integer', 'yellow': 'dolocationid', 'green': 'dolocationid'},
        {'name': 'payment_type', 'type': 'bigint', 'yellow': 'payment_type', 'green': 'payment_type'},
        {'name': 'hail_type', 'type': 'bigint', 'yellow': none, 'green': 'trip_type'},
        {'name': 'fare_amount', 'type': 'double precision', 'yellow': 'fare_amount', 'green': 'fare_amount'},
        {'name': 'extra', 'type': 'double precision', 'yellow': 'extra', 'green': 'extra'},
        {'name': 'mta_tax', 'type': 'double precision', 'yellow': 'mta_tax', 'green': 'mta_tax'},
        {'name': 'tip_amount', 'type': 'double precision', 'yellow': 'tip_amount', 'green': 'tip_amount'},
        {'name': 'tolls_amount', 'type': 'double precision', 'yellow': 'tolls_amount', 'green': 'tolls_amount'},
        {'name': 'ehail_fee', 'type': 'double precision', 'yellow': none, 'green': 'ehail_fee'},
        {'name': 'improvement_surcharge', 'type': 'double precision', 'yellow': 'improvement_surcharge', 'green': 'improvement_surcharge'},
        {'name': 'congestion_surcharge', 'type': 'double precision', 'yellow': 'congestion_surcharge', 'green': 'congestion_surcharge'},
        {'name': 'airport_fee', 'type': 'double precision', 'yellow': 'airport_fee', 'green': none},
        {'name': 'cbd_congestion_fee', 'type': 'double precision', 'yellow': 'cbd_congestion_fee', 'green': 'cbd_congestion_fee'},
        {'name': 'total_amount', 'type': 'double precision', 'yellow': 'total_amount', 'green': 'total_amount'},
        {'name': 'request_source', 'type': 'text', 'yellow': 'request_source', 'green': 'request_source'},
    ]) }}
{% endmacro %}

-- Landing metadata carried from bronze on (the landing contract of D34).
{% macro tlc_metadata_columns() %}
    {{ return([
        {'name': '_run_id', 'type': 'text'},
        {'name': '_source_uri', 'type': 'text'},
        {'name': '_etag', 'type': 'text'},
        {'name': '_chunk', 'type': 'integer'},
        {'name': '_loaded_at', 'type': 'timestamptz'},
    ]) }}
{% endmacro %}

-- Bronze for one trip type: every canonical column, cast from the landed column when the landing
-- table has it and NULL when it has never seen it (a column a later month added, or one this trip
-- type never publishes). Landing columns are read at build time, so a column EL Factory adds later
-- appears once bronze is rebuilt; the DAG rebuilds bronze on every run.
-- A landing table EL Factory has not created yet gives an empty view with the same columns.
{% macro tlc_bronze(trip_type) %}
    {%- set relation = source('ds_source', 'tlc_' ~ trip_type) -%}
    {%- set landed = [] -%}
    {%- set found = none -%}
    {%- if execute -%}
        {%- set found = adapter.get_relation(relation.database, relation.schema, relation.identifier) -%}
        {%- if found is not none -%}
            {%- for column in adapter.get_columns_in_relation(found) -%}
                {%- do landed.append(column.name | lower) -%}
            {%- endfor -%}
        {%- endif -%}
    {%- endif %}
select
    cast('{{ trip_type }}' as text) as trip_type,
    {%- if found is not none %}
    {{ tlc_month_of('_source_uri') }} as data_month,
    {%- else %}
    cast(null as text) as data_month,
    {%- endif %}
    {%- for column in tlc_columns() %}
    {%- set source_column = column[trip_type] %}
    {%- if found is not none and source_column is not none and source_column in landed %}
    cast({{ source_column }} as {{ column.type }}) as {{ column.name }},
    {%- else %}
    cast(null as {{ column.type }}) as {{ column.name }},
    {%- endif %}
    {%- endfor %}
    {%- for column in tlc_metadata_columns() %}
    {%- if found is not none %}
    {{ column.name }}{{ "," if not loop.last }}
    {%- else %}
    cast(null as {{ column.type }}) as {{ column.name }}{{ "," if not loop.last }}
    {%- endif %}
    {%- endfor %}
{%- if found is not none %}
from {{ relation }}
{%- else %}
where 1 = 0
{%- endif %}
{% endmacro %}

-- The data month a TLC file covers, from its name (<type>_tripdata_YYYY-MM.parquet).
-- dialect: Postgres substring(... from <regex>); BigQuery uses REGEXP_EXTRACT.
{% macro tlc_month_of(uri) -%}
    cast(substring({{ uri }} from '_([0-9]{4}-[0-9]{2})\.parquet$') as text)
{%- endmacro %}

-- The data month a build replaces, from `--vars '{data_month: YYYY-MM}'`; none builds every month.
{% macro tlc_data_month() %}
    {%- set month = var('data_month', none) -%}
    {%- if month is not none -%}
        {%- set month = month | string -%}
        {%- if not modules.re.match('^[0-9]{4}-(0[1-9]|1[0-2])$', month) -%}
            {{ exceptions.raise_compiler_error("var data_month must be YYYY-MM, got '" ~ month ~ "'") }}
        {%- endif -%}
    {%- endif -%}
    {{ return(month) }}
{% endmacro %}

-- `where` clause limiting a column (or expression) to the built month, or nothing when every month is built.
{% macro tlc_month_filter(column='data_month') %}
    {%- set month = tlc_data_month() -%}
    {%- if month is not none -%}
        where {{ column }} = '{{ month }}'
    {%- endif -%}
{% endmacro %}
