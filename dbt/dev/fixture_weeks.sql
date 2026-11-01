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
