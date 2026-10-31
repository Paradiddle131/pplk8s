-- Read-only roles for the semantic-layer agents (semantic/PLAN.md SL-4); lab-only passwords, like
-- the warehouse's own. Trust is the database's, not a prompt's: the semantic agent's MetricFlow
-- engine reads the semantic models' tables (silver) and the time spine as agent_metrics, and the
-- readiness ledger with its deadlines for the freshness of each answer; the text-to-SQL baseline
-- reads only gold and exposed as agent_sql. Default privileges reach tables dbt creates later.
-- Every data query either agent runs is audited in ops.agent_queries as agent_audit, which may
-- only insert there (SL-10): the agents' own roles write nothing, so no SQL a model writes can
-- forge or erase the audit.
-- Apply it after 01-schemas.sql to every database the agents read (up.sh: warehouse; the agent
-- eval: dbt_dev).
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
END
$$;
ALTER ROLE agent_metrics SET default_transaction_read_only = on;
ALTER ROLE agent_sql SET default_transaction_read_only = on;
ALTER ROLE agent_sql SET statement_timeout = '10s';
ALTER ROLE agent_audit SET statement_timeout = '5s';

CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS semantic;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS exposed;
CREATE SCHEMA IF NOT EXISTS ops;

GRANT USAGE ON SCHEMA silver, semantic TO agent_metrics;
GRANT SELECT ON ALL TABLES IN SCHEMA silver, semantic TO agent_metrics;
ALTER DEFAULT PRIVILEGES IN SCHEMA silver, semantic GRANT SELECT ON TABLES TO agent_metrics;
GRANT USAGE ON SCHEMA ops TO agent_metrics;
GRANT SELECT ON ops.readiness, ops.product_deadlines TO agent_metrics;

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
  metrics       text[],               -- query_metrics: the metrics asked for
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
