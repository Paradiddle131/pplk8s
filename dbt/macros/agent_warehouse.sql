-- The semantic agent's warehouse objects, wherever the dbt project builds (semantic/PLAN.md SL-4, SL-10;
-- #166): `dbt run-operation agent_warehouse`, or `make agent-warehouse` on the Compose warehouse.
-- Idempotent: every statement creates only what is missing and re-grants what exists, so re-run it after
-- a schema is dropped and rebuilt (its grants go with it) or after the readiness ledger appears.
--
-- Postgres: three lab-only logins, like the warehouse's own. Trust is the database's, not a prompt's:
--   - agent_metrics: the semantic agent's MetricFlow engine reads the semantic models' tables (silver) and
--     the time spine (semantic), plus the readiness ledger and its deadlines (ops.readiness,
--     ops.product_deadlines) for the freshness of each answer, when the Airflow lab created them;
--     without them the agent says "Freshness unknown".
--   - agent_sql: the eval's text-to-SQL baseline (SL-5, never deployed) reads only gold and exposed.
--   - agent_audit: may only insert into ops.agent_queries; the agents' own roles write nothing, so no SQL
--     a model writes can forge or erase the audit.
--   - outreach_automation: the partner outreach automation (dbt/models/exposed/consumers.yml), which reads
--     exposed.outreach_activation and its personal columns; no agent role reads a personal column
--     (agent_pii_columns.sql, SL-22), so this macro re-applies those column grants after its schema grants.
--   Default privileges reach tables dbt creates later, when dbt builds as the same user as this runs.
-- BigQuery: ops.agent_queries, and the readiness ledger and its deadlines when missing (ops.readiness,
-- ops.product_deadlines: the Compose init's on Postgres, platform/compose/warehouse-init/01-schemas.sql), whose
-- deadline rows it resets to that file's, so a new dataset answers with freshness. The agents' identities
-- and grants are IAM, one service account per deployed agent (docs/semantic-layer-on-bigquery.md, option A),
-- declared in platform/gcp/access.yaml.

{% macro agent_warehouse() -%}
  {#- Only a missing schema: BigQuery checks bigquery.datasets.create before it finds the dataset exists, and the
      dbt Job's service account holds no such grant on GCP, where infra/ creates every dataset. -#}
  {% for schema in ["silver", "semantic", "gold", "exposed", "ops"] %}
    {% if not adapter.check_schema_exists(target.database, schema) %}
      {% do adapter.create_schema(api.Relation.create(database=target.database, schema=schema)) %}
    {% endif %}
  {% endfor %}
  {{ return(adapter.dispatch("agent_warehouse")()) }}
{%- endmacro %}

{% macro default__agent_warehouse() -%}
  {% call statement("agent_warehouse") %}
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_metrics') THEN
    CREATE ROLE agent_metrics LOGIN PASSWORD 'agent_metrics';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_sql') THEN
    CREATE ROLE agent_sql LOGIN PASSWORD 'agent_sql';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_audit') THEN
    CREATE ROLE agent_audit LOGIN PASSWORD 'agent_audit';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'outreach_automation') THEN
    CREATE ROLE outreach_automation LOGIN PASSWORD 'outreach_automation';
  END IF;
END
$$;
ALTER ROLE agent_metrics SET default_transaction_read_only = on;
ALTER ROLE agent_sql SET default_transaction_read_only = on;
ALTER ROLE agent_sql SET statement_timeout = '10s';
ALTER ROLE agent_audit SET statement_timeout = '5s';
ALTER ROLE outreach_automation SET default_transaction_read_only = on;

GRANT USAGE ON SCHEMA silver, semantic TO agent_metrics;
GRANT SELECT ON ALL TABLES IN SCHEMA silver, semantic TO agent_metrics;
ALTER DEFAULT PRIVILEGES IN SCHEMA silver, semantic GRANT SELECT ON TABLES TO agent_metrics;
GRANT USAGE ON SCHEMA ops TO agent_metrics;
-- The readiness ledger belongs to the Airflow lab (platform/compose/warehouse-init/01-schemas.sql).
DO $$
BEGIN
  IF to_regclass('ops.readiness') IS NOT NULL THEN
    GRANT SELECT ON ops.readiness TO agent_metrics;
  END IF;
  IF to_regclass('ops.product_deadlines') IS NOT NULL THEN
    GRANT SELECT ON ops.product_deadlines TO agent_metrics;
  END IF;
END
$$;

GRANT USAGE ON SCHEMA gold, exposed TO agent_sql;
GRANT SELECT ON ALL TABLES IN SCHEMA gold, exposed TO agent_sql;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold, exposed GRANT SELECT ON TABLES TO agent_sql;
-- The automation's table grant comes with the model that names it in meta.pii_readers.
GRANT USAGE ON SCHEMA exposed TO outreach_automation;

-- One row per query_metrics or execute_sql call (services/semantic-agent/src/semantic_agent/audit.py).
CREATE TABLE IF NOT EXISTS ops.agent_queries (
  called_at     timestamptz NOT NULL DEFAULT now(),
  agent         text NOT NULL,        -- the ADK agent: semantic_agent or sql_baseline
  tool          text NOT NULL,        -- query_metrics or execute_sql
  user_id       text,
  session_id    text,
  invocation_id text,
  call_id       text,                 -- the model's function call id
  metrics       text[],               -- query_metrics: the metrics asked for, or its saved query's
  filters       jsonb,                -- query_metrics: {dimension, operator, values} conditions
  arguments     jsonb NOT NULL,       -- every argument as the model sent it (dates, group-bys)
  sql           text,                 -- the model's SQL, or the SQL MetricFlow compiled
  rows_returned integer,              -- null when the call returned an error
  freshness     text,                 -- the freshness statement the answer was told to quote
  error         text
);
REVOKE ALL ON ops.agent_queries FROM PUBLIC;
GRANT USAGE ON SCHEMA ops TO agent_audit;
GRANT INSERT ON ops.agent_queries TO agent_audit;
  {% endcall %}
  {% do agent_pii_columns_existing() %}
  {% do adapter.commit() %}
  {% do log("agent_warehouse: roles agent_metrics, agent_sql, agent_audit and outreach_automation, their grants, the personal columns' grants and ops.agent_queries in " ~ target.dbname, info=true) %}
{%- endmacro %}

{% macro bigquery__agent_warehouse() -%}
  {% set table = adapter.quote(target.database) ~ ".ops.agent_queries" %}
  {#- No column DEFAULT: BigQuery takes one, but the goccy emulator's parser refuses it (SL-7), so the
      writer sets called_at. -#}
  {% call statement("agent_warehouse") %}
create table if not exists {{ table }} (
  called_at     timestamp not null,
  agent         string not null,
  tool          string not null,
  user_id       string,
  session_id    string,
  invocation_id string,
  call_id       string,
  metrics       array<string>,
  filters       json,
  arguments     json not null,
  sql           string,
  rows_returned int64,
  freshness     string,
  error         string
)
  {% endcall %}
  {#- The readiness ledger and its deadlines (PLAN.md §3, D37), as 01-schemas.sql creates them on Postgres:
      no primary key (BigQuery enforces none) and no column default, so updated_at is the writer's. -#}
  {% call statement("agent_warehouse_readiness") %}
create table if not exists {{ adapter.quote(target.database) }}.ops.readiness (
  product        string not null,
  interval_start timestamp not null,
  interval_end   timestamp not null,
  watermark      timestamp,
  run_id         string not null,
  status         string not null,
  updated_at     timestamp not null,
  dag_id         string
)
  {% endcall %}
  {% call statement("agent_warehouse_deadlines") %}
create table if not exists {{ adapter.quote(target.database) }}.ops.product_deadlines (
  product string not null,
  max_age interval not null
)
  {% endcall %}
  {#- 01-schemas.sql's deadline rows, which it upserts (platform/gcp/tests/test_ops_tables.py holds the two
      lists equal): delete and insert rather than MERGE, whose source the emulator takes only as a table. -#}
  {% set deadlines = [
    ("sales", 36), ("marketing", 36), ("customer_actions", 36), ("partner_outreach", 36),
    ("recruitment", 36), ("call_transcripts", 36), ("finance.exposed", 36)
  ] %}
  {% set table = adapter.quote(target.database) ~ ".ops.product_deadlines" %}
  {% call statement("agent_warehouse_deadlines_reset") %}
delete from {{ table }} where product in ({% for product, _ in deadlines %}'{{ product }}'{{ ", " if not loop.last }}{% endfor %})
  {% endcall %}
  {% call statement("agent_warehouse_deadlines_insert") %}
insert into {{ table }} (product, max_age) values
{%- for product, hours in deadlines %}
  ('{{ product }}', interval {{ hours }} hour){{ "," if not loop.last }}
{%- endfor %}
  {% endcall %}
  {% do log("agent_warehouse: ops.agent_queries, ops.readiness and ops.product_deadlines (" ~ deadlines | length ~ " deadlines) in " ~ target.database ~ "; the agents' identities and grants are IAM (platform/gcp/access.yaml)", info=true) %}
{%- endmacro %}
