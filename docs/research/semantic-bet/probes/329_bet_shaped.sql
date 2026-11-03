-- bet_shaped: one table function per dbt saved query (models/semantic/saved_queries.yml), for the
-- `native-shaped` arm. Written once from MetricFlow's compiled BigQuery SQL (probes/329_shaped_sql.py,
-- dbt-metricflow 0.15.0, compiled 2026-11-03 with a sentinel date range) by a one-off edit read back by hand,
-- not by a generator: if this arm earns one, it is built then. Three changes only:
-- - the sentinel range became the arguments: `DATE(<day>) BETWEEN start_date AND end_date`, in every WHERE
--   MetricFlow put it (DATE() takes both TIMESTAMP and DATETIME, so the comparison holds on either column type);
-- - relations lost their project, so `silver.<table>` resolves in the project that holds bet_shaped;
-- - MetricFlow's comments were dropped; every aggregate, join, filter and ratio is MetricFlow's.
-- Run on the lab project as one script, after a dry run:
--   bq query --use_legacy_sql=false --dry_run < docs/research/semantic-bet/probes/329_bet_shaped.sql
-- Not yet run anywhere (2026-11-03): the lab project's live steps wait on its cost check.

CREATE SCHEMA IF NOT EXISTS bet_shaped OPTIONS (location = 'US');

-- Daily sales: What were revenue, orders, cancelled orders and distinct customers by day?
CREATE OR REPLACE TABLE FUNCTION bet_shaped.daily_sales(start_date DATE, end_date DATE)
OPTIONS (description = 'Revenue, orders, cancellations and distinct customers per day; the metrics behind gold.daily_sales. Question: What were revenue, orders, cancelled orders and distinct customers by day? Dates are inclusive.')
AS (
  WITH sma_10011_cte AS (
    SELECT
      TIMESTAMP_TRUNC(order_date, day) AS metric_time__day
      , status AS order__status
      , 1 AS __orders_total
      , CASE WHEN order_id IS NOT NULL THEN 1 ELSE 0 END AS __orders_cancelled
      , amount AS __revenue_eur
      , customer_id AS __customers_distinct
    FROM `silver`.`orders` orders_src_10000
  )

  SELECT
    COALESCE(subq_11.metric_time__day, subq_17.metric_time__day, subq_24.metric_time__day) AS metric_time__day
    , MAX(subq_11.revenue_eur) AS revenue_eur
    , MAX(subq_11.customers_distinct) AS customers_distinct
    , MAX(subq_17.orders_total) AS orders_total
    , MAX(subq_24.orders_cancelled) AS orders_cancelled
  FROM (
    SELECT
      metric_time__day
      , SUM(revenue_eur) AS revenue_eur
      , COUNT(DISTINCT customers_distinct) AS customers_distinct
    FROM (
      SELECT
        metric_time__day
        , order__status
        , __revenue_eur AS revenue_eur
        , __customers_distinct AS customers_distinct
      FROM sma_10011_cte
      WHERE DATE(metric_time__day) BETWEEN start_date AND end_date
    ) subq_7
    WHERE order__status <> 'cancelled'
    GROUP BY
      metric_time__day
  ) subq_11
  FULL OUTER JOIN (
    SELECT
      metric_time__day
      , SUM(__orders_total) AS orders_total
    FROM sma_10011_cte
    WHERE DATE(metric_time__day) BETWEEN start_date AND end_date
    GROUP BY
      metric_time__day
  ) subq_17
  ON
    subq_11.metric_time__day = subq_17.metric_time__day
  FULL OUTER JOIN (
    SELECT
      metric_time__day
      , SUM(orders_cancelled) AS orders_cancelled
    FROM (
      SELECT
        metric_time__day
        , order__status
        , __orders_cancelled AS orders_cancelled
      FROM sma_10011_cte
      WHERE DATE(metric_time__day) BETWEEN start_date AND end_date
    ) subq_20
    WHERE order__status = 'cancelled'
    GROUP BY
      metric_time__day
  ) subq_24
  ON
    COALESCE(subq_11.metric_time__day, subq_17.metric_time__day) = subq_24.metric_time__day
  GROUP BY
    metric_time__day
);

-- Net sales per day: What were revenue, returns and net revenue by day?
CREATE OR REPLACE TABLE FUNCTION bet_shaped.net_sales_daily(start_date DATE, end_date DATE)
OPTIONS (description = 'Revenue, partner returns and net revenue per day; finance\'s net sales, the metrics behind exposed.net_sales_daily. Question: What were revenue, returns and net revenue by day? Dates are inclusive.')
AS (
  WITH cm_4_cte AS (
    SELECT
      metric_time__day
      , SUM(revenue_eur) AS revenue_eur
    FROM (
      SELECT
        TIMESTAMP_TRUNC(order_date, day) AS metric_time__day
        , status AS order__status
        , amount AS revenue_eur
      FROM `silver`.`orders` orders_src_10000
      WHERE DATE(TIMESTAMP_TRUNC(order_date, day)) BETWEEN start_date AND end_date
    ) subq_5
    WHERE order__status <> 'cancelled'
    GROUP BY
      metric_time__day
  )

  , sma_10014_cte AS (
    SELECT
      TIMESTAMP_TRUNC(return_date, day) AS metric_time__day
      , amount AS __returns_eur
      , CASE WHEN return_id IS NOT NULL THEN 1 ELSE 0 END AS __returns_count
    FROM `silver`.`returns` returns_src_10000
  )

  SELECT
    COALESCE(cm_4_cte.metric_time__day, subq_16.metric_time__day, subq_25.metric_time__day) AS metric_time__day
    , MAX(cm_4_cte.revenue_eur) AS revenue_eur
    , MAX(subq_16.returns_count) AS returns_count
    , MAX(subq_16.returns_eur) AS returns_eur
    , MAX(subq_25.net_revenue_eur) AS net_revenue_eur
  FROM cm_4_cte
  FULL OUTER JOIN (
    SELECT
      metric_time__day
      , SUM(__returns_count) AS returns_count
      , SUM(__returns_eur) AS returns_eur
    FROM sma_10014_cte
    WHERE DATE(metric_time__day) BETWEEN start_date AND end_date
    GROUP BY
      metric_time__day
  ) subq_16
  ON
    cm_4_cte.metric_time__day = subq_16.metric_time__day
  FULL OUTER JOIN (
    SELECT
      metric_time__day
      , coalesce(revenue_eur, 0) - coalesce(returns_eur, 0) AS net_revenue_eur
    FROM (
      SELECT
        COALESCE(cm_4_cte.metric_time__day, subq_23.metric_time__day) AS metric_time__day
        , MAX(cm_4_cte.revenue_eur) AS revenue_eur
        , MAX(subq_23.returns_eur) AS returns_eur
      FROM cm_4_cte
      FULL OUTER JOIN (
        SELECT
          metric_time__day
          , SUM(__returns_eur) AS returns_eur
        FROM sma_10014_cte
        WHERE DATE(metric_time__day) BETWEEN start_date AND end_date
        GROUP BY
          metric_time__day
      ) subq_23
      ON
        cm_4_cte.metric_time__day = subq_23.metric_time__day
      GROUP BY
        metric_time__day
    ) subq_24
  ) subq_25
  ON
    COALESCE(cm_4_cte.metric_time__day, subq_16.metric_time__day) = subq_25.metric_time__day
  GROUP BY
    metric_time__day
);

-- Sales by country per day: What were revenue and orders by day and customer country?
CREATE OR REPLACE TABLE FUNCTION bet_shaped.sales_by_country_daily(start_date DATE, end_date DATE)
OPTIONS (description = 'Revenue and orders per day and customer country; the metrics behind exposed.sales_by_country_daily. Question: What were revenue and orders by day and customer country? Dates are inclusive.')
AS (
  WITH sma_10011_cte AS (
    SELECT
      TIMESTAMP_TRUNC(order_date, day) AS metric_time__day
      , customer_id AS customer
      , status AS order__status
      , 1 AS __orders_total
      , amount AS __revenue_eur
    FROM `silver`.`orders` orders_src_10000
  )

  , sma_10009_cte AS (
    SELECT
      customer_id AS customer
      , country
    FROM `silver`.`customers` customers_src_10000
  )

  SELECT
    COALESCE(subq_13.metric_time__day, subq_22.metric_time__day) AS metric_time__day
    , COALESCE(subq_13.customer__country, subq_22.customer__country) AS customer__country
    , MAX(subq_13.revenue_eur) AS revenue_eur
    , MAX(subq_22.orders_total) AS orders_total
  FROM (
    SELECT
      metric_time__day
      , customer__country
      , SUM(revenue_eur) AS revenue_eur
    FROM (
      SELECT
        subq_4.metric_time__day AS metric_time__day
        , subq_4.order__status AS order__status
        , sma_10009_cte.country AS customer__country
        , subq_4.__revenue_eur AS revenue_eur
      FROM (
        SELECT
          metric_time__day
          , customer
          , order__status
          , __revenue_eur
        FROM sma_10011_cte
        WHERE DATE(metric_time__day) BETWEEN start_date AND end_date
      ) subq_4
      LEFT OUTER JOIN
        sma_10009_cte
      ON
        subq_4.customer = sma_10009_cte.customer
    ) subq_9
    WHERE order__status <> 'cancelled'
    GROUP BY
      metric_time__day
      , customer__country
  ) subq_13
  FULL OUTER JOIN (
    SELECT
      subq_15.metric_time__day AS metric_time__day
      , sma_10009_cte.country AS customer__country
      , SUM(subq_15.__orders_total) AS orders_total
    FROM (
      SELECT
        metric_time__day
        , customer
        , __orders_total
      FROM sma_10011_cte
      WHERE DATE(metric_time__day) BETWEEN start_date AND end_date
    ) subq_15
    LEFT OUTER JOIN
      sma_10009_cte
    ON
      subq_15.customer = sma_10009_cte.customer
    GROUP BY
      metric_time__day
      , customer__country
  ) subq_22
  ON
    (
      subq_13.customer__country = subq_22.customer__country
    ) AND (
      subq_13.metric_time__day = subq_22.metric_time__day
    )
  GROUP BY
    metric_time__day
    , customer__country
);

-- Orders by status: How many orders are there in each status?
CREATE OR REPLACE TABLE FUNCTION bet_shaped.orders_by_status(start_date DATE, end_date DATE)
OPTIONS (description = 'Orders per status (placed, shipped, cancelled). Question: How many orders are there in each status? Dates are inclusive.')
AS (
  SELECT
    order__status
    , SUM(__orders_total) AS orders_total
  FROM (
    SELECT
      status AS order__status
      , 1 AS __orders_total
    FROM `silver`.`orders` orders_src_10000
    WHERE DATE(TIMESTAMP_TRUNC(order_date, day)) BETWEEN start_date AND end_date
  ) subq_5
  GROUP BY
    order__status
);

-- Returns by reason: How many partner returns were there, and how much did they cost, by reason?
CREATE OR REPLACE TABLE FUNCTION bet_shaped.returns_by_reason(start_date DATE, end_date DATE)
OPTIONS (description = 'Partner returns and their amount per return reason. Question: How many partner returns were there, and how much did they cost, by reason? Dates are inclusive.')
AS (
  SELECT
    return__reason
    , SUM(__returns_count) AS returns_count
    , SUM(__returns_eur) AS returns_eur
  FROM (
    SELECT
      reason AS return__reason
      , amount AS __returns_eur
      , CASE WHEN return_id IS NOT NULL THEN 1 ELSE 0 END AS __returns_count
    FROM `silver`.`returns` returns_src_10000
    WHERE DATE(TIMESTAMP_TRUNC(return_date, day)) BETWEEN start_date AND end_date
  ) subq_6
  GROUP BY
    return__reason
);

-- Damaged-goods returns per day: How many returns of damaged goods were there, and how much did they cost, by day?
CREATE OR REPLACE TABLE FUNCTION bet_shaped.damaged_returns_daily(start_date DATE, end_date DATE)
OPTIONS (description = 'Partner returns of damaged goods and their amount per day. Question: How many returns of damaged goods were there, and how much did they cost, by day? Dates are inclusive.')
AS (
  SELECT
    metric_time__day
    , SUM(returns_count) AS returns_count
    , SUM(returns_eur) AS returns_eur
  FROM (
    SELECT
      TIMESTAMP_TRUNC(return_date, day) AS metric_time__day
      , reason AS return__reason
      , amount AS returns_eur
      , CASE WHEN return_id IS NOT NULL THEN 1 ELSE 0 END AS returns_count
    FROM `silver`.`returns` returns_src_10000
    WHERE DATE(TIMESTAMP_TRUNC(return_date, day)) BETWEEN start_date AND end_date
  ) subq_5
  WHERE return__reason = 'damaged'
  GROUP BY
    metric_time__day
);

-- Channel performance: What were ad spend, leads, bookings, cost per lead and cost per booking by channel?
CREATE OR REPLACE TABLE FUNCTION bet_shaped.channel_performance(start_date DATE, end_date DATE)
OPTIONS (description = 'Ad spend, leads, bookings, cost per lead and cost per booking per marketing channel, as ratios of the period\'s totals. Question: What were ad spend, leads, bookings, cost per lead and cost per booking by channel? Dates are inclusive.')
AS (
  WITH rss_10006_cte AS (
    SELECT
      channel
      , campaign_id AS campaign
    FROM `silver`.`campaigns` campaigns_src_10000
  )

  , cm_5_cte AS (
    SELECT
      rss_10006_cte.channel AS campaign__channel
      , SUM(subq_5.__ad_spend_eur) AS ad_spend_eur
    FROM (
      SELECT
        campaign_id AS campaign
        , spend AS __ad_spend_eur
      FROM `silver`.`ad_spend` ad_spend_src_10000
      WHERE DATE(TIMESTAMP_TRUNC(spend_date, day)) BETWEEN start_date AND end_date
    ) subq_5
    LEFT OUTER JOIN
      rss_10006_cte
    ON
      subq_5.campaign = rss_10006_cte.campaign
    GROUP BY
      campaign__channel
  )

  , cm_6_cte AS (
    SELECT
      rss_10006_cte.channel AS campaign__channel
      , SUM(subq_15.__leads) AS leads
    FROM (
      SELECT
        campaign_id AS campaign
        , 1 AS __leads
      FROM `silver`.`leads` leads_src_10000
      WHERE DATE(TIMESTAMP_TRUNC(created_date, day)) BETWEEN start_date AND end_date
    ) subq_15
    LEFT OUTER JOIN
      rss_10006_cte
    ON
      subq_15.campaign = rss_10006_cte.campaign
    GROUP BY
      campaign__channel
  )

  , cm_7_cte AS (
    SELECT
      rss_10006_cte.channel AS campaign__channel
      , SUM(subq_25.__bookings) AS bookings
    FROM (
      SELECT
        campaign_id AS campaign
        , 1 AS __bookings
      FROM `silver`.`bookings` bookings_src_10000
      WHERE DATE(TIMESTAMP_TRUNC(booked_date, day)) BETWEEN start_date AND end_date
    ) subq_25
    LEFT OUTER JOIN
      rss_10006_cte
    ON
      subq_25.campaign = rss_10006_cte.campaign
    GROUP BY
      campaign__channel
  )

  SELECT
    COALESCE(cm_5_cte.campaign__channel, cm_6_cte.campaign__channel, cm_7_cte.campaign__channel, subq_35.campaign__channel, subq_39.campaign__channel) AS campaign__channel
    , MAX(cm_5_cte.ad_spend_eur) AS ad_spend_eur
    , MAX(cm_6_cte.leads) AS leads
    , MAX(cm_7_cte.bookings) AS bookings
    , MAX(CAST(subq_35.ad_spend_eur AS FLOAT64) / CAST(NULLIF(subq_35.leads, 0) AS FLOAT64)) AS cost_per_lead_eur
    , MAX(CAST(subq_39.ad_spend_eur AS FLOAT64) / CAST(NULLIF(subq_39.bookings, 0) AS FLOAT64)) AS cost_per_booking_eur
  FROM cm_5_cte
  FULL OUTER JOIN
    cm_6_cte
  ON
    cm_5_cte.campaign__channel = cm_6_cte.campaign__channel
  FULL OUTER JOIN
    cm_7_cte
  ON
    COALESCE(cm_5_cte.campaign__channel, cm_6_cte.campaign__channel) = cm_7_cte.campaign__channel
  FULL OUTER JOIN (
    SELECT
      COALESCE(cm_5_cte.campaign__channel, cm_6_cte.campaign__channel) AS campaign__channel
      , MAX(cm_5_cte.ad_spend_eur) AS ad_spend_eur
      , MAX(cm_6_cte.leads) AS leads
    FROM cm_5_cte
    FULL OUTER JOIN
      cm_6_cte
    ON
      cm_5_cte.campaign__channel = cm_6_cte.campaign__channel
    GROUP BY
      campaign__channel
  ) subq_35
  ON
    COALESCE(cm_5_cte.campaign__channel, cm_6_cte.campaign__channel, cm_7_cte.campaign__channel) = subq_35.campaign__channel
  FULL OUTER JOIN (
    SELECT
      COALESCE(cm_5_cte.campaign__channel, cm_7_cte.campaign__channel) AS campaign__channel
      , MAX(cm_5_cte.ad_spend_eur) AS ad_spend_eur
      , MAX(cm_7_cte.bookings) AS bookings
    FROM cm_5_cte
    FULL OUTER JOIN
      cm_7_cte
    ON
      cm_5_cte.campaign__channel = cm_7_cte.campaign__channel
    GROUP BY
      campaign__channel
  ) subq_39
  ON
    COALESCE(cm_5_cte.campaign__channel, cm_6_cte.campaign__channel, cm_7_cte.campaign__channel, subq_35.campaign__channel) = subq_39.campaign__channel
  GROUP BY
    campaign__channel
);
