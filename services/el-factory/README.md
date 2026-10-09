# EL Factory lite

EL Factory lite is the stand-in for the extraction service that runs on Cloud Run in production.
It fetches one page of a source per request, stages the page as NDJSON in object storage, and loads that staged file into the warehouse.
Airflow sees only HTTP; it never touches the source, the bucket, or the warehouse directly.

## Endpoints

- `GET /healthz` returns `200 {"status":"ok"}` and makes no dependency calls.
- `GET /catalog?pipeline=<name>` returns the enabled `[{"source", "entity"}]` pairs from `catalog.yaml`; entries marked `enabled: false` are left out.
  It answers 400 when `pipeline` is missing and 404 when the pipeline is unknown.
- `POST /extract` with the JSON body `{source, entity, run_id, interval_start, interval_end, cursor?}` extracts one page.
  Timestamps are ISO-8601 with a timezone offset; the interval is half-open `[start, end)`.
  A `cursor` query parameter overrides the body cursor.
  The response is `{"status":"ok","source","entity","page","rows","object","next_url"}`.
  Callers POST the same body to `next_url` until it is `null`.

Every error is JSON: `{"status":"error","retryable":<bool>,"error":"..."}`.
Validation failures are 400, and unknown pipelines, sources, or entities are 404.
Transient failures are 503 with `retryable: true`: injected failures, Open-Meteo 5xx or connection errors, dropped warehouse connections, and GCS 5xx or 429 responses.
An Open-Meteo 4xx means our request is wrong, so it is a 502 with `retryable: false`.
Any other failure is 500 with `retryable: false`.

## Processing

1. The request is validated; `run_id` must match `[A-Za-z0-9_.:+-]+`.
2. `FAIL_RATE` is applied before any work, so a retry drill never leaves partial state.
3. The page is fetched from the source.
4. The page is staged to `gs://<GCS_BUCKET>/<source>/<entity>/<run_id>/page-<NNNNN>.jsonl`, overwriting any earlier object.
5. The staged object is downloaded and parsed, and its rows are loaded.
   The load deletes the rows for `(_run_id, _interval_start, _interval_end, _page)` and inserts the new ones in one transaction, under an advisory lock, so re-running a request leaves row counts unchanged.
   Page 0 deletes every page of that `(_run_id, _interval_start, _interval_end)`, so a re-run that yields fewer pages leaves no stale rows behind.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `WAREHOUSE_DSN` | required | Postgres DSN, for example `postgresql://warehouse:warehouse@warehouse:5432/warehouse` |
| `STORAGE_EMULATOR_HOST` | unset | When set, the GCS client uses anonymous credentials against this host, for example `http://gcs:4443` |
| `GCS_BUCKET` | `staging` | Bucket for staged pages |
| `GCP_PROJECT` | `pplk8s` | GCP project passed to the storage client |
| `PAGE_SIZE` | `100` | Rows per page for the synthetic sources |
| `FAIL_RATE` | `0` | Probability in `[0, 1]` that `/extract` returns a retryable 503 before doing any work |
| `CATALOG_PATH` | `catalog.yaml` next to the package | Catalog file, validated at startup |
| `OPEN_METEO_URL` | `https://archive-api.open-meteo.com/v1/archive` | Open-Meteo archive endpoint, overridable for tests |
| `PORT` | `8080` | Port the image's gunicorn binds to |

## Sources

- `synthetic.customers` is a fixed snapshot of 200 customers, identical for every interval.
- `synthetic.orders` is generated per UTC day from a seed of that day, so an order's content never depends on the interval that requested it.
- `open_meteo.hourly_weather` fetches hourly temperature and precipitation for Amsterdam, Istanbul, and London, one page per location.

All synthetic output is deterministic and all data is synthetic or public.

## Warehouse contract

The tables live in schema `ds_source` and are created with `CREATE TABLE IF NOT EXISTS` for every registered entity at startup (best effort) and again before each load, so dbt sources resolve even before an entity's first extract.
The schema itself must already exist; `warehouse-init` creates it in the Compose stack.
Every table ends with the metadata columns `_run_id text`, `_interval_start timestamptz`, `_interval_end timestamptz`, `_page integer`, `_source_uri text`, and `_loaded_at timestamptz DEFAULT now()`.
All metadata columns except `_loaded_at` are `NOT NULL`.
Each table also has the index `<table>_load_key_idx` on `(_run_id, _interval_start, _interval_end, _page)`.

| Table | Columns |
|---|---|
| `ds_source.synthetic_customers` | `customer_id integer`, `name text`, `email text`, `country text`, `signup_date date` |
| `ds_source.synthetic_orders` | `order_id text`, `customer_id integer`, `order_ts timestamptz`, `status text`, `amount numeric(12,2)`, `currency text` |
| `ds_source.open_meteo_hourly_weather` | `location text`, `latitude numeric(8,4)`, `longitude numeric(8,4)`, `observed_at timestamptz`, `temperature_c numeric(5,2)`, `precipitation_mm numeric(6,2)` |

## Tests

```bash
cd services/el-factory
uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

The unit tests use in-memory fakes for storage and the warehouse and mock the Open-Meteo HTTP call, so they need no network and no services.

## Image

```bash
docker build -t localhost:5001/el-factory:0.1.0 services/el-factory
docker run --rm localhost:5001/el-factory:0.1.0 id -u   # prints 10001
```

The image is multi-stage, runs as uid 10001, exposes 8080, and has a `/healthz` health check.
It runs gunicorn with two workers and the control socket disabled, because that socket is an admin feature the container does not need.
