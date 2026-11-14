-- What it measures (Q7): whether one row access policy still filters rows read through a view, a table
-- function and an authorized table function, for the identity the policy names.
-- How to run: through probes/332_rls_check.sh (live, the lab project), which substitutes @ME@ with
-- SESSION_USER() and runs each statement on its own (every statement ends with a line holding only ';').
-- Synthetic rows: 6 orders, 3 in DE, 2 in FR, 1 in US; the policy grants @ME@ the DE rows.
-- Right answers if the policy holds on a path: 3 rows and 60 in amount; 6 rows and 150 if the path bypasses it.

CREATE SCHEMA IF NOT EXISTS bet_rls OPTIONS (location = 'US')
;
CREATE SCHEMA IF NOT EXISTS bet_rls_api OPTIONS (location = 'US')
;
-- Rows go in before the policy: DML needs the TRUE filter once a table has a policy.
CREATE OR REPLACE TABLE bet_rls.orders (order_id STRING, country STRING, amount NUMERIC)
AS SELECT * FROM UNNEST([
  STRUCT('o1' AS order_id, 'DE' AS country, NUMERIC '10' AS amount),
  ('o2', 'DE', 20), ('o3', 'DE', 30), ('o4', 'FR', 40), ('o5', 'FR', 25), ('o6', 'US', 25)
])
;
CREATE OR REPLACE VIEW bet_rls.orders_v AS SELECT order_id, country, amount FROM bet_rls.orders
;
CREATE OR REPLACE TABLE FUNCTION bet_rls.orders_tf(min_amount NUMERIC)
AS SELECT order_id, country, amount FROM bet_rls.orders WHERE amount >= min_amount
;
-- In another dataset, so authorizing it on bet_rls (the runner patches bet_rls's access list) is what lets
-- a caller without table access read through it.
CREATE OR REPLACE TABLE FUNCTION bet_rls_api.orders_auth_tf(min_amount NUMERIC)
AS SELECT order_id, country, amount FROM bet_rls.orders WHERE amount >= min_amount
;
CREATE OR REPLACE ROW ACCESS POLICY bet_de ON bet_rls.orders
GRANT TO ('@ME@') FILTER USING (country = 'DE')
;
SELECT 'table' AS path, COUNT(*) AS n, SUM(amount) AS amount FROM bet_rls.orders
UNION ALL SELECT 'view', COUNT(*), SUM(amount) FROM bet_rls.orders_v
UNION ALL SELECT 'table function', COUNT(*), SUM(amount) FROM bet_rls.orders_tf(0)
UNION ALL SELECT 'authorized table function', COUNT(*), SUM(amount) FROM bet_rls_api.orders_auth_tf(0)
ORDER BY path
;
