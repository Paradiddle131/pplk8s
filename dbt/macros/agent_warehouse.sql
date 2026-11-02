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
--   - agent_metrics_de: agent_metrics scoped to Germany's customers, their orders and returns (SL-21): its
--     scope is a row of ops.agent_scopes, which the row policies of agent_row_scope.sql read through
--     ops.agent_countries(role); this macro applies those policies to the scoped tables that exist.
--   Default privileges reach tables dbt creates later, when dbt builds as the same user as this runs.
-- BigQuery: ops.agent_queries only. The agents' identities and grants are IAM, one service account per
-- deployed agent (docs/semantic-layer-on-bigquery.md, option A), which the lab leaves out of scope.

{% macro agent_warehouse() -%}
  {% for schema in ["silver", "semantic", "gold", "exposed", "ops"] %}
    {% do adapter.create_schema(api.Relation.create(database=target.database, schema=schema)) %}
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
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_metrics_de') THEN
    CREATE ROLE agent_metrics_de LOGIN PASSWORD 'agent_metrics_de';
  END IF;
END
$$;
ALTER ROLE agent_metrics SET default_transaction_read_only = on;
ALTER ROLE agent_metrics_de SET default_transaction_read_only = on;
ALTER ROLE agent_sql SET default_transaction_read_only = on;
ALTER ROLE agent_sql SET statement_timeout = '10s';
ALTER ROLE agent_audit SET statement_timeout = '5s';

GRANT USAGE ON SCHEMA silver, semantic TO agent_metrics;
GRANT SELECT ON ALL TABLES IN SCHEMA silver, semantic TO agent_metrics;
ALTER DEFAULT PRIVILEGES IN SCHEMA silver, semantic GRANT SELECT ON TABLES TO agent_metrics;
GRANT USAGE ON SCHEMA ops TO agent_metrics;
-- agent_metrics_de: the same grants; the row policies, not the grants, limit what it reads.
GRANT USAGE ON SCHEMA silver, semantic TO agent_metrics_de;
GRANT SELECT ON ALL TABLES IN SCHEMA silver, semantic TO agent_metrics_de;
ALTER DEFAULT PRIVILEGES IN SCHEMA silver, semantic GRANT SELECT ON TABLES TO agent_metrics_de;
GRANT USAGE ON SCHEMA ops TO agent_metrics_de;
-- The readiness ledger belongs to the Airflow lab (platform/compose/warehouse-init/01-schemas.sql).
DO $$
BEGIN
  IF to_regclass('ops.readiness') IS NOT NULL THEN
    GRANT SELECT ON ops.readiness TO agent_metrics, agent_metrics_de;
  END IF;
  IF to_regclass('ops.product_deadlines') IS NOT NULL THEN
    GRANT SELECT ON ops.product_deadlines TO agent_metrics, agent_metrics_de;
  END IF;
END
$$;

-- Row scopes (SL-21): a role's countries; a role without a row reads every row. The function is the only
-- way a policy or an agent reads them (security definer: no role needs a grant on the table).
CREATE TABLE IF NOT EXISTS ops.agent_scopes (
  role      name PRIMARY KEY,
  countries text[] NOT NULL
);
REVOKE ALL ON ops.agent_scopes FROM PUBLIC;
INSERT INTO ops.agent_scopes (role, countries) VALUES ('agent_metrics_de', '{DE}')
  ON CONFLICT (role) DO UPDATE SET countries = excluded.countries;
CREATE OR REPLACE FUNCTION ops.agent_countries(agent name) RETURNS text[]
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
  AS $fn$ SELECT countries FROM ops.agent_scopes WHERE role = agent $fn$;
REVOKE ALL ON FUNCTION ops.agent_countries(name) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.agent_countries(name) TO PUBLIC;

GRANT USAGE ON SCHEMA gold, exposed TO agent_sql;
GRANT SELECT ON ALL TABLES IN SCHEMA gold, exposed TO agent_sql;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold, exposed GRANT SELECT ON TABLES TO agent_sql;

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
-- The scope statement the answer was told to quote, when the agent's role is scoped (SL-21).
ALTER TABLE ops.agent_queries ADD COLUMN IF NOT EXISTS scope text;
REVOKE ALL ON ops.agent_queries FROM PUBLIC;
GRANT USAGE ON SCHEMA ops TO agent_audit;
GRANT INSERT ON ops.agent_queries TO agent_audit;
  {% endcall %}
  {% for name, rule in agent_row_scopes().items() %}
    {% set node = graph.nodes.values() | selectattr("resource_type", "equalto", "model") | selectattr("name", "equalto", name) | first %}
    {% set relation = adapter.get_relation(database=node.database, schema=node.schema, identifier=node.alias) %}
    {% if relation is not none %}
      {% do run_query(default__agent_row_scope(relation, rule)) %}
    {% endif %}
  {% endfor %}
  {% do adapter.commit() %}
  {% do log("agent_warehouse: roles agent_metrics, agent_metrics_de, agent_sql and agent_audit, their grants, row scopes and ops.agent_queries in " ~ target.dbname, info=true) %}
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
  error         string,
  scope         string
)
  {% endcall %}
  {% do log("agent_warehouse: ops.agent_queries in " ~ target.database ~ "; the agents' identities and grants are IAM, out of the lab's scope", info=true) %}
{%- endmacro %}
