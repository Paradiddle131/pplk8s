-- DEV-ONLY fixture: six more weeks of sales and marketing, 2026-08-17 (a Monday) to 2026-09-30, the day
-- before dbt/dev/fixture.sql's first day, so the semantic layer's period-over-period and to-date metrics
-- have weeks and months to compare (semantic/PLAN.md SL-1).
-- Load it after fixture.sql, never alone: it inserts into the tables fixture.sql creates, and fixture.sql
-- reloaded drops these rows again. It leaves fixture.sql's days untouched, so a check scoped to
-- 2026-10-01 onwards keeps its numbers:
--   docker exec -i pplk8s-warehouse-1 psql -U warehouse -d dbt_dev -v ON_ERROR_STOP=1 < dbt/dev/fixture_weeks.sql
-- Every value comes from a fixed formula of the day's index i (0 to 44) and week w (i / 7, 0 to 6), so the
-- fixture is reproducible: revenue grows week on week except a dip in the fourth week (w = 3), the search
-- campaign's leads step up from the fifth week, and each day lands as its own run, loaded 30 to 40 minutes
-- after the day ends. The values are synthetic.

-- Orders: 3 to 5 a day for customers 1 to 10; one in nine cancelled, every second one shipped.
INSERT INTO ds_source.synthetic_orders
SELECT
    'ORD-W' || to_char(d.day, 'MMDD') || '-' || k,
    ((d.i * 7 + k * 3) % 10) + 1,
    d.day + make_interval(hours => 7 + 3 * k),
    CASE WHEN (d.i * 3 + k) % 9 = 0 THEN 'cancelled' WHEN k % 2 = 0 THEN 'shipped' ELSE 'placed' END,
    (30 + 8 * d.w + ((d.i * 37 + k * 53) % 120) + ((d.i + k) % 4) * 0.25
        - CASE WHEN d.w = 3 THEN 25 ELSE 0 END)::numeric(12,2),
    'EUR',
    'run-w-' || to_char(d.day, 'YYYYMMDD'),
    d.day, d.day + interval '1 day', 1, 'fixture://orders',
    d.day + interval '1 day 30 minutes'
FROM (SELECT i, i / 7 AS w, timestamptz '2026-08-17 00:00+00' + make_interval(days => i) AS day
      FROM generate_series(0, 44) AS i) AS d
CROSS JOIN LATERAL generate_series(1, 3 + d.i % 3) AS k;

-- Ad spend: every day for the three campaigns of fixture.sql; search's spend grows 5.00 a week.
INSERT INTO ds_source.synthetic_ad_spend
SELECT
    d.day::date,
    c.campaign_id,
    (s.spend * 80)::integer,
    (s.spend * 5 / 2)::integer,
    s.spend,
    'EUR',
    'run-mkt-w-' || to_char(d.day, 'YYYYMMDD'),
    d.day, d.day + interval '1 day', 1, 'fixture://ad_spend',
    d.day + interval '1 day 40 minutes'
FROM (SELECT i, i / 7 AS w, timestamptz '2026-08-17 00:00+00' + make_interval(days => i) AS day
      FROM generate_series(0, 44) AS i) AS d
CROSS JOIN (VALUES (1), (4), (7)) AS c(campaign_id)
CROSS JOIN LATERAL (SELECT (CASE c.campaign_id
    WHEN 1 THEN 90 + (d.i % 5) * 10 + 5 * d.w
    WHEN 4 THEN 60 + (d.i % 3) * 10
    ELSE 10 END)::numeric(12,2) AS spend) AS s;

-- Budget snapshots: each campaign's month budget (search 6000.00, social 4000.00, email 400.00) less its
-- spend in the month up to and including the day, from the spend just inserted.
INSERT INTO ds_source.synthetic_campaign_budgets
SELECT
    spend_date,
    campaign_id,
    budget,
    budget - sum(spend) OVER (PARTITION BY campaign_id, date_trunc('month', spend_date) ORDER BY spend_date),
    'run-mkt-w-' || to_char(spend_date, 'YYYYMMDD'),
    spend_date, spend_date + 1, 1, 'fixture://campaign_budgets',
    spend_date + interval '1 day 40 minutes'
FROM (SELECT spend_date, campaign_id, spend,
             (CASE campaign_id WHEN 1 THEN 6000 WHEN 4 THEN 4000 ELSE 400 END)::numeric(12,2) AS budget
      FROM ds_source.synthetic_ad_spend WHERE spend_date BETWEEN '2026-08-17' AND '2026-09-30') AS s;

-- Leads: search 2 or 3 a day (one more from the fifth week), social 1 or 2, email one every fourth day.
-- A lead whose (day + number + campaign) is divisible by 3 books five hours later, the same day.
CREATE TEMP TABLE fixture_weeks_leads AS
SELECT
    'L-W' || to_char(d.day, 'MMDD') || '-' || c.campaign_id || '-' || n AS lead_id,
    c.campaign_id,
    d.day + make_interval(hours => 7 + n) AS created_ts,
    CASE c.campaign_id WHEN 4 THEN 'TR' ELSE 'NL' END AS country,
    d.day,
    d.i,
    n
FROM (SELECT i, i / 7 AS w, timestamptz '2026-08-17 00:00+00' + make_interval(days => i) AS day
      FROM generate_series(0, 44) AS i) AS d
CROSS JOIN (VALUES (1), (4), (7)) AS c(campaign_id)
CROSS JOIN LATERAL generate_series(1, CASE c.campaign_id
    WHEN 1 THEN 2 + d.i % 2 + CASE WHEN d.w >= 4 THEN 1 ELSE 0 END
    WHEN 4 THEN 1 + CASE WHEN d.i % 3 = 0 THEN 1 ELSE 0 END
    ELSE CASE WHEN d.i % 4 = 0 THEN 1 ELSE 0 END END) AS n;

INSERT INTO ds_source.synthetic_leads
SELECT lead_id, campaign_id, created_ts, country,
       'run-mkt-w-' || to_char(day, 'YYYYMMDD'), day, day + interval '1 day', 1, 'fixture://leads',
       day + interval '1 day 40 minutes'
FROM fixture_weeks_leads;

INSERT INTO ds_source.synthetic_bookings
SELECT 'B-W' || substr(lead_id, 4), lead_id, created_ts + interval '5 hours',
       (1500 + ((i * 11 + n * 7 + campaign_id) % 20) * 100)::numeric(12,2), 'EUR',
       'run-mkt-w-' || to_char(day, 'YYYYMMDD'), day, day + interval '1 day', 1, 'fixture://bookings',
       day + interval '1 day 40 minutes'
FROM fixture_weeks_leads
WHERE (i + n + campaign_id) % 3 = 0;

-- Customers 11 to 30 sign up every third day from 2026-08-01 to 2026-09-27 (two months of signups), and
-- every third of them (12, 15, ..., 30) places a first order after the base fixture's days, from 2026-10-04,
-- so no figure above moves: 24, 27 and 30 order 29, 21 and 13 days after signing up (within 30 days; 29 is the
-- window's last day), 12 to 21 between 37 and 61 days after. Their countries cycle through the six accepted.
INSERT INTO ds_source.synthetic_customers
SELECT
    c,
    'Customer ' || c,
    'customer' || c || '@example.test',
    (ARRAY['NL', 'TR', 'GB', 'DE', 'FR', 'US'])[1 + c % 6],
    date '2026-08-01' + (c - 11) * 3,
    'run-c-w-' || c,
    timestamptz '2026-08-01 00:00+00' + make_interval(days => (c - 11) * 3),
    timestamptz '2026-08-02 00:00+00' + make_interval(days => (c - 11) * 3),
    1, 'fixture://customers',
    timestamptz '2026-08-02 00:30+00' + make_interval(days => (c - 11) * 3)
FROM generate_series(11, 30) AS c;

INSERT INTO ds_source.synthetic_orders
SELECT
    'ORD-S' || c,
    c,
    timestamptz '2026-10-04 10:00+00' + make_interval(days => (c - 12) / 3),
    'placed',
    (20 + c)::numeric(12,2),
    'EUR',
    'run-s-' || c,
    timestamptz '2026-10-04 00:00+00' + make_interval(days => (c - 12) / 3),
    timestamptz '2026-10-05 00:00+00' + make_interval(days => (c - 12) / 3),
    1, 'fixture://orders',
    timestamptz '2026-10-05 00:30+00' + make_interval(days => (c - 12) / 3)
FROM generate_series(12, 30, 3) AS c;

-- Three returns of the six weeks' orders, recorded on 5 and 6 October (after the base fixture's days), so a
-- return rate on the order's date has August and September returns: 0828-1 damaged, 0914-1 damaged, 0921-2
-- wrong size.
INSERT INTO ds_source.partner_returns VALUES
    ('R-W1', 'ORD-W0914-1', '2026-10-05 09:00+00', 20.00, 'damaged', 'gcs-run-w', 'gs://landing/returns/2026-10-05.jsonl', 1, '2026-10-06 06:00+00'),
    ('R-W2', 'ORD-W0921-2', '2026-10-05 11:00+00', 15.00, 'wrong size', 'gcs-run-w', 'gs://landing/returns/2026-10-05.jsonl', 1, '2026-10-06 06:00+00'),
    ('R-W3', 'ORD-W0828-1', '2026-10-06 10:00+00', 30.00, 'damaged', 'gcs-run-w2', 'gs://landing/returns/2026-10-06.jsonl', 1, '2026-10-07 06:00+00');
