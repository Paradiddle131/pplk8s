-- Read-only roles for the semantic-layer agents (semantic/PLAN.md SL-4); lab-only passwords, like
-- the warehouse's own. Trust is the database's, not a prompt's: the semantic agent's MetricFlow
-- engine reads the semantic models' tables (silver) and the time spine as agent_metrics, and the
-- readiness ledger with its deadlines for the freshness of each answer; the text-to-SQL baseline
-- reads only gold and exposed as agent_sql. Default privileges reach tables dbt creates later.
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
END
$$;
ALTER ROLE agent_metrics SET default_transaction_read_only = on;
ALTER ROLE agent_sql SET default_transaction_read_only = on;
ALTER ROLE agent_sql SET statement_timeout = '10s';

CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS semantic;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS exposed;

GRANT USAGE ON SCHEMA silver, semantic TO agent_metrics;
GRANT SELECT ON ALL TABLES IN SCHEMA silver, semantic TO agent_metrics;
ALTER DEFAULT PRIVILEGES IN SCHEMA silver, semantic GRANT SELECT ON TABLES TO agent_metrics;
GRANT USAGE ON SCHEMA ops TO agent_metrics;
GRANT SELECT ON ops.readiness, ops.product_deadlines TO agent_metrics;

GRANT USAGE ON SCHEMA gold, exposed TO agent_sql;
GRANT SELECT ON ALL TABLES IN SCHEMA gold, exposed TO agent_sql;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold, exposed GRANT SELECT ON TABLES TO agent_sql;
