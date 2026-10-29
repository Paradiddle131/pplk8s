-- DEV-ONLY fixture for the dbt project. Never run against the lab's `warehouse` database.
-- Usage (creates the schemas and loads the synthetic ds_source rows into dbt_dev):
--   docker exec -i pplk8s-warehouse-1 psql -U warehouse -d dbt_dev -v ON_ERROR_STOP=1 < dbt/dev/fixture.sql
-- The values are synthetic; they are not Open-Meteo or customer data.
-- Re-running this file resets the four ds_source tables (CASCADE drops the bronze views over them); dbt rebuilds the layers.

CREATE SCHEMA IF NOT EXISTS ds_source;
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS exposed;
CREATE SCHEMA IF NOT EXISTS semantic;

DROP TABLE IF EXISTS ds_source.synthetic_customers CASCADE;
DROP TABLE IF EXISTS ds_source.synthetic_orders CASCADE;
DROP TABLE IF EXISTS ds_source.open_meteo_hourly_weather CASCADE;
DROP TABLE IF EXISTS ds_source.partner_returns CASCADE;

CREATE TABLE ds_source.synthetic_customers (
    customer_id integer,
    name text,
    email text,
    country text,
    signup_date date,
    _run_id text,
    _interval_start timestamptz,
    _interval_end timestamptz,
    _page integer,
    _source_uri text,
    _loaded_at timestamptz
);

CREATE TABLE ds_source.synthetic_orders (
    order_id text,
    customer_id integer,
    order_ts timestamptz,
    status text,
    amount numeric(12,2),
    currency text,
    _run_id text,
    _interval_start timestamptz,
    _interval_end timestamptz,
    _page integer,
    _source_uri text,
    _loaded_at timestamptz
);

CREATE TABLE ds_source.open_meteo_hourly_weather (
    location text,
    latitude numeric(8,4),
    longitude numeric(8,4),
    observed_at timestamptz,
    temperature_c numeric(5,2),
    precipitation_mm numeric(6,2),
    _run_id text,
    _interval_start timestamptz,
    _interval_end timestamptz,
    _page integer,
    _source_uri text,
    _loaded_at timestamptz
);

-- Customers: run-cust-1 is the first full snapshot; run-cust-2 re-lands all 10 customers
-- and renames customer 3, so silver must keep the later name.
INSERT INTO ds_source.synthetic_customers VALUES
    (1,  'Ada Jansen',        'ada.jansen@example.test',     'NL', '2024-01-15', 'run-cust-1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://customers', '2026-10-01 00:20+00'),
    (2,  'Mehmet Yilmaz',     'mehmet.yilmaz@example.test',  'TR', '2024-02-03', 'run-cust-1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://customers', '2026-10-01 00:20+00'),
    (3,  'Oliver Smith',      'oliver.smith@example.test',   'GB', '2024-02-20', 'run-cust-1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://customers', '2026-10-01 00:20+00'),
    (4,  'Lena Schmidt',      'lena.schmidt@example.test',   'DE', '2024-03-11', 'run-cust-1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://customers', '2026-10-01 00:20+00'),
    (5,  'Marc Dupont',       'marc.dupont@example.test',    'FR', '2024-04-02', 'run-cust-1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://customers', '2026-10-01 00:20+00'),
    (6,  'Emma Johnson',      'emma.johnson@example.test',   'US', '2024-05-19', 'run-cust-1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://customers', '2026-10-01 00:20+00'),
    (7,  'Sanne de Vries',    'sanne.devries@example.test',  'NL', '2024-06-30', 'run-cust-1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://customers', '2026-10-01 00:20+00'),
    (8,  'Ayse Kaya',         'ayse.kaya@example.test',      'TR', '2024-07-08', 'run-cust-1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://customers', '2026-10-01 00:20+00'),
    (9,  'Tom Brown',         'tom.brown@example.test',      'GB', '2024-08-14', 'run-cust-1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://customers', '2026-10-01 00:20+00'),
    (10, 'Julia Weber',       'julia.weber@example.test',    'DE', '2024-09-01', 'run-cust-1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://customers', '2026-10-01 00:20+00'),
    (1,  'Ada Jansen',        'ada.jansen@example.test',     'NL', '2024-01-15', 'run-cust-2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://customers', '2026-10-03 00:20+00'),
    (2,  'Mehmet Yilmaz',     'mehmet.yilmaz@example.test',  'TR', '2024-02-03', 'run-cust-2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://customers', '2026-10-03 00:20+00'),
    (3,  'Oliver Smith-Jones','oliver.smith@example.test',   'GB', '2024-02-20', 'run-cust-2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://customers', '2026-10-03 00:20+00'),
    (4,  'Lena Schmidt',      'lena.schmidt@example.test',   'DE', '2024-03-11', 'run-cust-2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://customers', '2026-10-03 00:20+00'),
    (5,  'Marc Dupont',       'marc.dupont@example.test',    'FR', '2024-04-02', 'run-cust-2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://customers', '2026-10-03 00:20+00'),
    (6,  'Emma Johnson',      'emma.johnson@example.test',   'US', '2024-05-19', 'run-cust-2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://customers', '2026-10-03 00:20+00'),
    (7,  'Sanne de Vries',    'sanne.devries@example.test',  'NL', '2024-06-30', 'run-cust-2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://customers', '2026-10-03 00:20+00'),
    (8,  'Ayse Kaya',         'ayse.kaya@example.test',      'TR', '2024-07-08', 'run-cust-2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://customers', '2026-10-03 00:20+00'),
    (9,  'Tom Brown',         'tom.brown@example.test',      'GB', '2024-08-14', 'run-cust-2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://customers', '2026-10-03 00:20+00'),
    (10, 'Julia Weber',       'julia.weber@example.test',    'DE', '2024-09-01', 'run-cust-2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://customers', '2026-10-03 00:20+00');

-- Orders: run-d1 covers 2026-10-01, run-d2 covers 2026-10-02.
-- ORD-0007 is re-extracted by run-d1-rerun (loaded later) with status shipped; silver must keep that row.
INSERT INTO ds_source.synthetic_orders VALUES
    ('ORD-0001', 1,  '2026-10-01 08:12+00', 'placed',    25.00,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0002', 2,  '2026-10-01 09:40+00', 'shipped',  120.50,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0003', 3,  '2026-10-01 10:05+00', 'cancelled', 60.00,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0004', 4,  '2026-10-01 11:30+00', 'placed',    15.75,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0005', 5,  '2026-10-01 12:00+00', 'shipped',  210.00,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0006', 1,  '2026-10-01 13:20+00', 'placed',    45.00,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0007', 6,  '2026-10-01 14:10+00', 'placed',    80.00,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0008', 7,  '2026-10-01 15:45+00', 'shipped',   33.30,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0009', 8,  '2026-10-01 16:00+00', 'cancelled', 99.99,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0010', 9,  '2026-10-01 17:30+00', 'placed',    12.00,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0011', 10, '2026-10-01 18:05+00', 'shipped',  300.00,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0012', 2,  '2026-10-01 19:40+00', 'placed',    47.25,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0013', 3,  '2026-10-01 20:15+00', 'shipped',   18.90,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0014', 4,  '2026-10-01 21:00+00', 'placed',    64.00,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0015', 5,  '2026-10-01 22:30+00', 'placed',     9.99,  'EUR', 'run-d1', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-02 00:30+00'),
    ('ORD-0007', 6,  '2026-10-01 14:10+00', 'shipped',   80.00,  'EUR', 'run-d1-rerun', '2026-10-01 00:00+00', '2026-10-02 00:00+00', 1, 'fixture://orders', '2026-10-03 06:00+00'),
    ('ORD-0016', 6,  '2026-10-02 07:00+00', 'placed',    22.00,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0017', 7,  '2026-10-02 08:15+00', 'shipped',  140.00,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0018', 8,  '2026-10-02 09:30+00', 'placed',    58.50,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0019', 9,  '2026-10-02 10:45+00', 'cancelled', 77.00,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0020', 10, '2026-10-02 11:10+00', 'shipped',   31.00,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0021', 1,  '2026-10-02 12:00+00', 'placed',    19.95,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0022', 2,  '2026-10-02 13:25+00', 'shipped',  250.00,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0023', 3,  '2026-10-02 14:50+00', 'placed',    42.00,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0024', 4,  '2026-10-02 15:30+00', 'cancelled', 12.50,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0025', 5,  '2026-10-02 16:05+00', 'placed',    88.80,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0026', 6,  '2026-10-02 17:40+00', 'shipped',   65.00,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0027', 7,  '2026-10-02 18:20+00', 'placed',     5.00,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0028', 8,  '2026-10-02 19:10+00', 'shipped',  110.00,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0029', 9,  '2026-10-02 20:55+00', 'placed',    36.40,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00'),
    ('ORD-0030', 10, '2026-10-02 22:00+00', 'cancelled', 49.00,  'EUR', 'run-d2', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1, 'fixture://orders', '2026-10-03 00:30+00');

-- Weather: 2 locations x 2 days x 12 observations (every 2 hours UTC) = 48 rows.
-- Values come from a fixed formula, so the fixture is reproducible.
INSERT INTO ds_source.open_meteo_hourly_weather
SELECT
    loc.location,
    loc.latitude,
    loc.longitude,
    ts.observed_at,
    round((loc.base_temp + 5 * sin(extract(hour FROM ts.observed_at) / 24.0 * 2 * pi()))::numeric, 2),
    round((CASE WHEN extract(hour FROM ts.observed_at) BETWEEN 10 AND 16 THEN loc.rain_peak ELSE 0 END)::numeric, 2),
    'run-weather-1',
    '2026-10-01 00:00+00',
    '2026-10-03 00:00+00',
    1,
    'fixture://weather',
    '2026-10-03 01:00+00'
FROM (VALUES
    ('Amsterdam', 52.3676::numeric, 4.9041::numeric, 11.0::numeric, 0.6::numeric),
    ('Istanbul',  41.0082::numeric, 28.9784::numeric, 19.0::numeric, 0.0::numeric)
) AS loc(location, latitude, longitude, base_temp, rain_peak)
CROSS JOIN generate_series(
    '2026-10-01 00:00+00'::timestamptz,
    '2026-10-02 22:00+00'::timestamptz,
    interval '2 hours'
) AS ts(observed_at);

-- Partner returns: file returns/2026-10-01.jsonl landed twice; generation 2 replaced generation 1
-- in ds_source (so only its rows remain), and a second file covers 2026-10-02.
CREATE TABLE ds_source.partner_returns (
    return_id text,
    order_id text,
    returned_at timestamptz,
    amount numeric(12,2),
    reason text,
    _run_id text,
    _source_uri text,
    _generation bigint,
    _loaded_at timestamptz
);

INSERT INTO ds_source.partner_returns VALUES
    ('R-1', 'O-1', '2026-10-01 10:00+00', 12.50, 'damaged', 'gcs-run-a', 'gs://landing/returns/2026-10-01.jsonl', 2, '2026-10-02 06:00+00'),
    ('R-2', 'O-2', '2026-10-01 15:30+00', 5.00, 'wrong size', 'gcs-run-a', 'gs://landing/returns/2026-10-01.jsonl', 2, '2026-10-02 06:00+00'),
    ('R-3', 'O-3', '2026-10-02 09:15+00', 7.25, 'late delivery', 'gcs-run-b', 'gs://landing/returns/2026-10-02.jsonl', 1, '2026-10-03 06:00+00');
