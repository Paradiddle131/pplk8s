-- DEV-ONLY: completes version y2 of yellow 2025-01 on top of tlc_fixture.sql, the way EL Factory
-- finishes a republished file (D34): the last chunk lands, ops.file_versions gets the version,
-- and the older version's landed rows are dropped (its file_versions row stays, as in EL Factory). Rebuilding 2025-01 must then show only y2's 253 yellow rows (2 + 1 + 250 generated, all clean).
-- Usage: docker exec -i pplk8s-warehouse-1 psql -U warehouse -d dbt_dev -v ON_ERROR_STOP=1 < dbt/dev/tlc_republish.sql

BEGIN;
INSERT INTO ds_source.tlc_yellow (
  _run_id, _source_uri, _etag, _chunk, _loaded_at, vendorid, tpep_pickup_datetime, tpep_dropoff_datetime,
  passenger_count, trip_distance, ratecodeid, store_and_fwd_flag, pulocationid, dolocationid, payment_type,
  fare_amount, extra, mta_tax, tip_amount, tolls_amount, improvement_surcharge, total_amount,
  congestion_surcharge, airport_fee, cbd_congestion_fee
) VALUES
  ('fixture__2025-01', 'fixture://trip-data/yellow_tripdata_2025-01.parquet', '"y2"', 1, '2026-10-02 00:00+00',
   2, '2025-01-04 10:00', '2025-01-04 10:11', 1, 2.5, 1, 'N', 264, 236, 1,
   8.5, 1.0, 0.5, 2.0, 0.0, 1.0, 17.0, 2.5, 0.0, 0.75);
INSERT INTO ds_source.tlc_yellow (
  _run_id, _source_uri, _etag, _chunk, _loaded_at, vendorid, tpep_pickup_datetime, tpep_dropoff_datetime,
  passenger_count, trip_distance, ratecodeid, store_and_fwd_flag, pulocationid, dolocationid, payment_type,
  fare_amount, extra, mta_tax, tip_amount, tolls_amount, improvement_surcharge, total_amount,
  congestion_surcharge, airport_fee, cbd_congestion_fee
)
SELECT
  'fixture__2025-01', 'fixture://trip-data/yellow_tripdata_2025-01.parquet', '"y2"', 2, '2026-10-02 00:00+00',
  1, timestamp '2025-01-01 00:40' + n * interval '2 hours', timestamp '2025-01-01 00:55' + n * interval '2 hours',
  1, 1.2, 1, 'N', 230 + n % 10, 236, 1,
  10.0, 1.0, 0.5, 2.0, 0.0, 1.0, 17.0, 2.5, 0.0, 0.75
FROM generate_series(0, 249) AS n;
INSERT INTO ops.file_versions (source_uri, etag, completed_at)
  VALUES ('fixture://trip-data/yellow_tripdata_2025-01.parquet', '"y2"', '2026-10-02 00:05+00');
DELETE FROM ds_source.tlc_yellow
  WHERE _source_uri = 'fixture://trip-data/yellow_tripdata_2025-01.parquet' AND _etag <> '"y2"';
COMMIT;
