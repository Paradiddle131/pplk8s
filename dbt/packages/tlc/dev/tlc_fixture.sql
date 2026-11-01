-- DEV-ONLY fixture for the tlc models (PLAN.md D34-D36). Never run against the lab's `warehouse` database.
-- Usage: docker exec -i pplk8s-warehouse-1 psql -U warehouse -d dbt_dev -v ON_ERROR_STOP=1 < dbt/dev/tlc_fixture.sql
-- Rows are synthetic, shaped like the landed TLC files (D34 landing contract: lower-cased published
-- columns plus _run_id, _source_uri, _etag, _chunk, _loaded_at). Re-running resets the tlc tables.
--
-- Scenario (tests/e2e/tlc-dbt-check.sh asserts it):
--   yellow 2024-12  version y1, complete:  5 + 250 clean + 1 negative fare
--   yellow 2025-01  version y1, complete:  3 + 250 clean + one row per other rule (pickup outside month,
--                                          dropoff before pickup, over 24 h)
--   yellow 2025-01  version y2, chunk 0 only, not completed: 2 rows that must stay invisible
--   green  2024-12  version g1, complete:  2 clean
--   green  2025-01  version g1, complete:  3 clean + 1 negative total
-- The green table has no request_source column (no 2026-06+ file landed), so bronze fills it with NULL.
-- The 250 generated clean rows per month keep the quarantined share under the 2 % warning (D36).
-- tlc_republish.sql then completes y2 for 2025-01.

CREATE SCHEMA IF NOT EXISTS ds_source;
CREATE SCHEMA IF NOT EXISTS ops;

-- CASCADE drops the bronze views over the landing tables; the tlc tables dbt built go too, so every
-- run of the scenario starts from nothing.
DROP TABLE IF EXISTS ds_source.tlc_yellow CASCADE;
DROP TABLE IF EXISTS ds_source.tlc_green CASCADE;
DROP TABLE IF EXISTS ops.file_versions;
DROP VIEW IF EXISTS exposed.tlc_daily_trips_by_borough;
DROP TABLE IF EXISTS gold.tlc_daily_trips;
DROP TABLE IF EXISTS silver.tlc_trips;
DROP TABLE IF EXISTS silver.tlc_trips_quarantine;

-- Same DDL as platform/compose/warehouse-init/01-schemas.sql.
CREATE TABLE ops.file_versions (
  source_uri   text        NOT NULL,
  etag         text        NOT NULL,
  completed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (source_uri, etag)
);

CREATE TABLE ds_source.tlc_yellow (
  _run_id text NOT NULL, _source_uri text NOT NULL, _etag text NOT NULL, _chunk integer NOT NULL,
  _loaded_at timestamptz NOT NULL DEFAULT now(),
  vendorid integer, tpep_pickup_datetime timestamp, tpep_dropoff_datetime timestamp,
  passenger_count double precision, trip_distance double precision, ratecodeid double precision,
  store_and_fwd_flag text, pulocationid bigint, dolocationid bigint, payment_type bigint,
  fare_amount double precision, extra double precision, mta_tax double precision, tip_amount double precision,
  tolls_amount double precision, improvement_surcharge double precision, total_amount double precision,
  congestion_surcharge double precision, airport_fee double precision, cbd_congestion_fee double precision,
  request_source text
);

CREATE TABLE ds_source.tlc_green (
  _run_id text NOT NULL, _source_uri text NOT NULL, _etag text NOT NULL, _chunk integer NOT NULL,
  _loaded_at timestamptz NOT NULL DEFAULT now(),
  vendorid integer, lpep_pickup_datetime timestamp, lpep_dropoff_datetime timestamp, store_and_fwd_flag text,
  ratecodeid bigint, pulocationid integer, dolocationid integer, passenger_count bigint,
  trip_distance double precision, fare_amount double precision, extra double precision, mta_tax double precision,
  tip_amount double precision, tolls_amount double precision, ehail_fee double precision,
  improvement_surcharge double precision, total_amount double precision, payment_type bigint, trip_type bigint,
  congestion_surcharge double precision, cbd_congestion_fee double precision
);

-- Yellow: (uri suffix, etag, chunk, pickup, dropoff, pickup zone, fare, total, cbd fee)
INSERT INTO ds_source.tlc_yellow (
  _run_id, _source_uri, _etag, _chunk, _loaded_at, vendorid, tpep_pickup_datetime, tpep_dropoff_datetime,
  passenger_count, trip_distance, ratecodeid, store_and_fwd_flag, pulocationid, dolocationid, payment_type,
  fare_amount, extra, mta_tax, tip_amount, tolls_amount, improvement_surcharge, total_amount,
  congestion_surcharge, airport_fee, cbd_congestion_fee
)
SELECT
  'fixture__' || t.month, 'fixture://trip-data/yellow_tripdata_' || t.month || '.parquet', t.etag, t.chunk,
  '2026-10-01 00:00+00', 2, t.pickup::timestamp, t.dropoff::timestamp,
  1.0, 2.5, 1.0, 'N', t.zone, 236, 1,
  t.fare, 1.0, 0.5, 2.0, 0.0, 1.0, t.total,
  2.5, 0.0, t.cbd
FROM (VALUES
  ('2024-12', '"y1"', 0, '2024-12-01 08:00', '2024-12-01 08:20', 161, 12.0, 19.0, NULL),
  ('2024-12', '"y1"', 0, '2024-12-05 09:00', '2024-12-05 09:30', 161, 20.0, 27.0, NULL),
  ('2024-12', '"y1"', 0, '2024-12-10 10:00', '2024-12-10 10:10', 132, 8.0, 15.0, NULL),
  ('2024-12', '"y1"', 1, '2024-12-20 11:00', '2024-12-20 11:45', 132, 45.0, 60.0, NULL),
  ('2024-12', '"y1"', 1, '2024-12-31 23:50', '2025-01-01 00:10', 1, 30.0, 40.0, NULL),
  ('2024-12', '"y1"', 1, '2024-12-15 12:00', '2024-12-15 12:05', 161, -5.0, -3.0, NULL),
  ('2025-01', '"y1"', 0, '2025-01-02 08:00', '2025-01-02 08:20', 161, 12.0, 20.5, 0.75),
  ('2025-01', '"y1"', 0, '2025-01-03 09:00', '2025-01-03 09:30', 132, 20.0, 28.5, 0.75),
  ('2025-01', '"y1"', 0, '2025-01-04 10:00', '2025-01-04 10:10', 264, 8.0, 16.5, 0.75),
  ('2025-01', '"y1"', 1, '2024-12-31 22:00', '2024-12-31 22:30', 161, 15.0, 22.0, 0.75),
  ('2025-01', '"y1"', 1, '2025-01-05 12:00', '2025-01-05 11:00', 161, 10.0, 17.0, 0.75),
  ('2025-01', '"y1"', 1, '2025-01-06 12:00', '2025-01-07 13:00', 161, 90.0, 99.0, 0.75),
  ('2025-01', '"y2"', 0, '2025-01-02 08:00', '2025-01-02 08:21', 161, 12.5, 21.0, 0.75),
  ('2025-01', '"y2"', 0, '2025-01-03 09:00', '2025-01-03 09:31', 132, 20.5, 29.0, 0.75)
) AS t(month, etag, chunk, pickup, dropoff, zone, fare, total, cbd);

-- 250 generated clean yellow trips per month in chunk 2 of version y1, one every 2 hours.
INSERT INTO ds_source.tlc_yellow (
  _run_id, _source_uri, _etag, _chunk, _loaded_at, vendorid, tpep_pickup_datetime, tpep_dropoff_datetime,
  passenger_count, trip_distance, ratecodeid, store_and_fwd_flag, pulocationid, dolocationid, payment_type,
  fare_amount, extra, mta_tax, tip_amount, tolls_amount, improvement_surcharge, total_amount,
  congestion_surcharge, airport_fee, cbd_congestion_fee
)
SELECT
  'fixture__' || m.month, 'fixture://trip-data/yellow_tripdata_' || m.month || '.parquet', '"y1"', 2,
  '2026-10-01 00:00+00', 1, m.start + n * interval '2 hours', m.start + n * interval '2 hours' + interval '15 minutes',
  1.0, 1.2, 1.0, 'N', 230 + n % 10, 236, 1,
  10.0, 1.0, 0.5, 2.0, 0.0, 1.0, 17.0,
  2.5, 0.0, m.cbd
FROM (VALUES ('2024-12', timestamp '2024-12-01 00:30', NULL::double precision),
             ('2025-01', timestamp '2025-01-01 00:30', 0.75)) AS m(month, start, cbd)
CROSS JOIN generate_series(0, 249) AS n;

INSERT INTO ds_source.tlc_green (
  _run_id, _source_uri, _etag, _chunk, _loaded_at, vendorid, lpep_pickup_datetime, lpep_dropoff_datetime,
  store_and_fwd_flag, ratecodeid, pulocationid, dolocationid, passenger_count, trip_distance, fare_amount,
  extra, mta_tax, tip_amount, tolls_amount, ehail_fee, improvement_surcharge, total_amount, payment_type,
  trip_type, congestion_surcharge, cbd_congestion_fee
)
SELECT
  'fixture__' || t.month, 'fixture://trip-data/green_tripdata_' || t.month || '.parquet', '"g1"', 0,
  '2026-10-01 00:00+00', 2, t.pickup::timestamp, t.dropoff::timestamp,
  'N', 1, t.zone, 74, 1, 1.8, t.fare,
  0.5, 0.5, 1.0, 0.0, NULL, 1.0, t.total, 1,
  t.hail, 0.0, t.cbd
FROM (VALUES
  ('2024-12', '2024-12-02 07:00', '2024-12-02 07:15', 74, 9.0, 12.0, 1, NULL),
  ('2024-12', '2024-12-03 07:00', '2024-12-03 07:25', 75, 14.0, 17.0, 2, NULL),
  ('2025-01', '2025-01-02 07:00', '2025-01-02 07:15', 74, 9.0, 12.75, 1, 0.75),
  ('2025-01', '2025-01-03 07:00', '2025-01-03 07:25', 75, 14.0, 17.75, 1, 0.75),
  ('2025-01', '2025-01-04 07:00', '2025-01-04 07:35', 41, 18.0, 21.75, 2, 0.75),
  ('2025-01', '2025-01-05 07:00', '2025-01-05 07:05', 41, 3.0, -1.0, 1, 0.75)
) AS t(month, pickup, dropoff, zone, fare, total, hail, cbd);

INSERT INTO ops.file_versions (source_uri, etag, completed_at) VALUES
  ('fixture://trip-data/yellow_tripdata_2024-12.parquet', '"y1"', '2026-10-01 00:05+00'),
  ('fixture://trip-data/yellow_tripdata_2025-01.parquet', '"y1"', '2026-10-01 00:05+00'),
  ('fixture://trip-data/green_tripdata_2024-12.parquet', '"g1"', '2026-10-01 00:05+00'),
  ('fixture://trip-data/green_tripdata_2025-01.parquet', '"g1"', '2026-10-01 00:05+00');
