-- Written by probes/331_graph_measures.py from the project's manifest.
CREATE SCHEMA IF NOT EXISTS bet_graph OPTIONS (location = 'US');

CREATE OR REPLACE PROPERTY GRAPH bet_graph.sales
  NODE TABLES (
    silver.customers AS customers
      KEY (customer_id)
      PROPERTIES (customer_id, country, signup_date, MEASURE(COUNT(customer_id)) AS signups),
    silver.orders AS orders
      KEY (order_id)
      PROPERTIES (order_id, amount, currency, customer_id, order_date, status, MEASURE(SAFE_DIVIDE(AGG(orders_cancelled), NULLIF(AGG(orders_total), 0))) AS cancellation_rate, MEASURE(COUNT(DISTINCT CASE WHEN (status <> 'cancelled') THEN customer_id END)) AS customers_distinct, MEASURE(COUNT(CASE WHEN (status = 'cancelled') THEN order_id END)) AS orders_cancelled, MEASURE(COUNT(order_id)) AS orders_total, MEASURE(SUM(CASE WHEN (status <> 'cancelled') THEN amount END)) AS revenue_eur),
    silver.returns AS returns
      KEY (return_id)
      PROPERTIES (return_id, amount, order_date, reason, return_date, MEASURE(COUNT(return_id)) AS returns_count, MEASURE(SUM(amount)) AS returns_eur, MEASURE(COUNT(return_id)) AS returns_on_order_date)
  )
  EDGE TABLES (
    silver.orders AS orders_to_customers
      KEY (order_id)
      SOURCE KEY (order_id) REFERENCES orders (order_id)
      DESTINATION KEY (customer_id) REFERENCES customers (customer_id),
    silver.returns AS returns_to_orders
      KEY (return_id)
      SOURCE KEY (return_id) REFERENCES returns (return_id)
      DESTINATION KEY (order_id) REFERENCES orders (order_id),
    silver.returns AS returns_to_customers
      KEY (return_id)
      SOURCE KEY (return_id) REFERENCES returns (return_id)
      DESTINATION KEY (customer_id) REFERENCES customers (customer_id)
  );
