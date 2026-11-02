# EL Factory lite

EL Factory lite is the stand-in for the extraction service that runs on Cloud Run in production.
It fetches one page of a source per request, stages the page as NDJSON in object storage, and loads that staged file into the warehouse.
Airflow sees only HTTP; it never touches the source, the bucket, or the warehouse directly.

## Endpoints

- `GET /healthz` returns `200 {"status":"ok"}` and makes no dependency calls.
- `GET /catalog?pipeline=<name>` returns the enabled `[{"source", "entity"}]` pairs from `catalog.yaml`; entries marked `enabled: false` are left out.
  It answers 400 when `pipeline` is missing and 404 when the pipeline is unknown.
- `POST /extract` with the JSON body `{source, entity, run_id, interval_start, interval_end, cursor?}` extracts pages from `cursor` on until `MAX_RUN_TIME` is spent (PLAN.md D34).
  Timestamps are ISO-8601 with a timezone offset; the interval is half-open `[start, end)`.
  A `cursor` query parameter overrides the body cursor.
  The response is `{"status":"ok","source","entity","page","pages","rows","object","next_url"}`: `page` is the cursor the request started at, `pages` and `rows` count what it loaded, and `object` is the last page it staged.
  Callers POST the same body to `next_url` until it is `null`.
- `GET /publication?source=tlc&entity=<e>&month=YYYY-MM` asks whether a file source's month is published, with one `HEAD` and no download: 200 `{"status": "published", "source_uri", "etag", "size"}`, or 200 `{"status": "not_published", "source_uri"}` when S3 answers `AccessDenied`.
  A CloudFront block is a retryable 503, never `not_published` (issue #36); a source that is not file-backed is 400.
- `GET /months?source=tlc&entity=<e>` lists the data months the chunk ledgers hold for a file source, loading or complete, oldest first: 200 `{"source", "entity", "months": ["YYYY-MM", ...]}` (PLAN.md D35).
- `POST /retire` with the JSON body `{source, entity, keep: ["YYYY-MM", ...]}` retires every held month not in `keep`: it deletes the month's landed rows (every version) and its `ops.file_chunks` and `ops.file_versions` rows, so a later load of that month starts over (issue #87).
  The response is `{"status":"ok","source","entity","kept","retired":[{"month","rows"}],"rows"}`; an empty or malformed `keep` is 400, because retiring everything is never what a caller means.
  The caller owns the policy and EL Factory only deletes; on BigQuery the same retirement is the month partition's expiration.
- `/publication`, `/months`, `/retire` and `/extract` of source `tlc` are the file sources' (`el_factory/tlc`, a Flask blueprint), served only where the warehouse keeps their ledger (`FileLedger`, Postgres only) and the build carries `el_factory/tlc` with pyarrow (the `files` extra; semantic/PLAN.md SL-19).
  Elsewhere they are 404, and `/catalog` leaves out their entries and the `tlc` pipeline.
- `POST /load` with the JSON body `{entity, bucket, object, generation, run_id}` loads one landed NDJSON file into `ds_source.<entity>`.
  `generation` is the GCS object generation as a decimal string or integer; EL Factory reads exactly that generation.
  The response is `{"status":"ok","entity","object","generation","rows"}`, with `object` as a `gs://` URI and `generation` as a string.

Every error is JSON: `{"status":"error","retryable":<bool>,"error":"..."}`.
Validation failures are 400, and unknown pipelines, sources, or entities are 404.
Transient failures are 503 with `retryable: true`: injected failures, Open-Meteo 5xx or connection errors, dropped warehouse connections, and GCS 5xx or 429 responses.
An Open-Meteo 4xx means our request is wrong, so it is a 502 with `retryable: false`.
Any other failure is 500 with `retryable: false`.
`POST /load` adds two non-retryable cases.
A file that breaks its entity's contract is 422.
A generation that is no longer live, or older than one already loaded, is 409 with `"superseded": true`: the newer generation has its own object event, so the caller should skip rather than fail.

## Processing

1. The request is validated; `run_id` must match `[A-Za-z0-9_.:+-]+`.
2. `FAIL_RATE` is applied before any work, so a retry drill never leaves partial state.
3. The page is fetched from the source.
4. The page is staged to `gs://<GCS_BUCKET>/<source>/<entity>/<run_id>/page-<NNNNN>.jsonl`, overwriting any earlier object.
5. The staged object is downloaded and parsed, and its rows are loaded.
   The load deletes the rows for `(_run_id, _interval_start, _interval_end, _page)` and inserts the new ones in one transaction, under an advisory lock, so re-running a request leaves row counts unchanged.
   Page 0 deletes every page of that `(_run_id, _interval_start, _interval_end)`, so a re-run that yields fewer pages leaves no stale rows behind.
6. Steps 3 to 5 repeat for the next page until the source has none or `MAX_RUN_TIME` has passed since the request began.
   The budget is checked between pages, so the first page always runs and a request can overrun by one page.

### Loading a file

1. The request is validated, and `FAIL_RATE` applies as for `/extract`.
2. The object is read at the requested generation.
   On a bucket without versioning only the live generation is readable, so an overwritten generation is superseded.
3. Every line must be a JSON object with exactly the entity's columns; one bad line rejects the whole file and loads nothing.
4. Under an advisory lock per object, the load deletes every row of that object and inserts the new rows in one transaction.
   Reloading a generation leaves row counts unchanged, a newer generation replaces the rows instead of adding to them, and an older generation never overwrites a newer one.

### Extracting a file source (tlc)

`POST /extract` for source `tlc` fetches the file itself instead of paging an API (PLAN.md D34).
The interval must be exactly one calendar month; the file is `<TLC_BASE_URL>/<entity>_tripdata_<YYYY-MM>.parquet`.

1. A `HEAD` reads the file's `ETag` and size; S3's 403 `AccessDenied` (`Server: AmazonS3`) is 502 with `"published": false`, and CloudFront's own 403 block is a retryable 503.
2. The resume point is the first chunk (Parquet row group) `ops.file_chunks` has not recorded for that `ETag`; the request's cursor is informational.
   So a retry without a cursor redoes at most the chunk that was in flight, and a republished file (new `ETag`) starts over at chunk 0.
   A pending chunk over 64 MiB compressed is 422 non-retryable before anything else happens: staging costs about four times a chunk's compressed size, so FHVHV 2023-01's single 451 MiB row group would be OOMKilled on every retry (#90).
3. The file's schema is compared with `ds_source.tlc_<entity>`: every typed column lands under its lower-cased name, new columns are added, integer widens to bigint and then to double precision, and any other type change is 502 non-retryable. All-null columns are left out until a file gives them a type.
4. Each chunk is read with one ranged GET (`If-Match: <ETag>`; a 412 means the file changed and is a retryable 503), staged to `gs://<GCS_BUCKET>/tlc/<entity>/<YYYY-MM>/<etag>/chunk-<NNNNN>.parquet`, and loaded from the staged object with `COPY` in 25,000-row batches (each batch is copied several times on its way into `COPY`, so larger batches cost memory without speed; #90).
   The chunk's rows and its `ops.file_chunks` row are written in one transaction, so a chunk is either loaded and recorded or neither.
5. Chunks repeat until the file is done or `MAX_RUN_TIME` is spent, as for paged sources; at most one chunk per process is in flight, to stay under the 1 GiB memory ceiling (D35).
6. The last chunk writes `ops.file_versions` and deletes every other version's rows and chunk records for that file.
   The response adds `source_uri`, `etag` and `chunks` (the file's row-group count); `page` is the first chunk the request loaded.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `ELF_WAREHOUSE` | `postgres` (the image's `WAREHOUSE`) | The warehouse implementation (`el_factory/warehouse.py`); any other value fails at startup |
| `WAREHOUSE_DSN` | required on Postgres | Postgres DSN, for example `postgresql://warehouse:warehouse@warehouse:5432/warehouse` |
| `STORAGE_EMULATOR_HOST` | unset | When set, the GCS client uses anonymous credentials against this host, for example `http://gcs:4443` |
| `GCS_BUCKET` | `staging` | Bucket for staged pages |
| `GCP_PROJECT` | `pplk8s`; required on BigQuery | GCP project of the storage client and of the BigQuery warehouse |
| `BQ_API_ENDPOINT` | unset | On BigQuery: the BigQuery emulator's endpoint (no credentials), for example `http://localhost:9050` |
| `GCP_ACCESS_TOKEN` | unset | On BigQuery: an access token where a proxy injects the real one (cloud sessions); unset, application default credentials |
| `BQ_MAXIMUM_BYTES_BILLED` | `1073741824` | On BigQuery: the bytes one query job may bill (free-path.yaml's `caps.bigquery_maximum_bytes_billed`) |
| `PAGE_SIZE` | `100` | Rows per page for the synthetic sources |
| `FAIL_RATE` | `0` | Probability in `[0, 1]` that `/extract` returns a retryable 503 before doing any work |
| `MAX_RUN_TIME` | `45` | Seconds one `/extract` request keeps loading pages before it answers `next_url`; `0` gives one page per request. Keep it at most half the caller's read timeout (120 s in `ElFactoryHook`) |
| `CATALOG_PATH` | `catalog.yaml` next to the package | Catalog file, validated at startup |
| `OPEN_METEO_URL` | `https://archive-api.open-meteo.com/v1/archive` | Open-Meteo archive endpoint, overridable for tests |
| `TLC_BASE_URL` | `https://d37ci6vzurychx.cloudfront.net/trip-data` | Where the TLC trip files live; the only egress host the `tlc` source needs |
| `PORT` | `8080` | Port the image's gunicorn binds to |

## Sources

- `synthetic.customers` is a fixed snapshot of 200 customers, identical for every interval.
- `synthetic.orders` is generated per UTC day from a seed of that day, so an order's content never depends on the interval that requested it.
- `synthetic.campaigns` is a fixed snapshot of 8 ad campaigns; `synthetic.ad_spend` has one row per campaign per UTC day whose midnight is in the interval; `synthetic.leads` are generated per UTC day from a seed of that day; `synthetic.bookings` are the leads that book (about 30 %), within 21 days of the lead, each decided by the lead's own seed (PLAN.md D38).
- `open_meteo.hourly_weather` fetches hourly temperature and precipitation for Amsterdam, Istanbul, and London, one page per location.

- `tlc.yellow`, `tlc.green` and `tlc.fhvhv` are the NYC TLC trip record files, one Parquet file per data month; FHVHV is disabled in the catalog and kept for the big-file drill (D35). Source facts: [`docs/research/tlc-source-facts.md`](../../docs/research/tlc-source-facts.md) (issue #36).

All synthetic output is deterministic and all data is synthetic or public; TLC data is downloaded at run time and never committed.

## Warehouse contract

The app reaches the warehouse only through the `Warehouse` protocol in `el_factory/warehouse.py` (semantic/PLAN.md SL-19): `ELF_WAREHOUSE` picks the implementation, and only its module, with its driver, is imported, so an image built for one warehouse carries no other's driver.
`postgres` (`warehouse_postgres.py`, the `postgres` extra) is the lab's Compose warehouse; `bigquery` (`warehouse_bigquery.py`, the `bigquery` extra) is the lab project's ([#227](../../../../issues/227)).
The file sources need more than a `Warehouse`: the `FileLedger` protocol in the same module (chunked landing tables, the chunk and version ledgers, retirement), which only `warehouse_postgres.py` implements.
Every driver error leaves the implementation as a `WarehouseError` whose `transient` flag decides the answer: a dropped or refused connection is a retryable 503, anything else a 500.
The contract below is Postgres's; BigQuery's differs only as follows.

- `ds_source` is a dataset the infrastructure creates; each table is created from the same columns, typed for BigQuery (`text` as `STRING`, `integer` as `INT64`, `numeric(p,s)` as `NUMERIC`, `timestamptz` as `TIMESTAMP`), with the same metadata columns, `REQUIRED` where Postgres has `NOT NULL`, and no index.
- Rows go in by a load job (free), never by a streaming insert, which has no free tier: a page's or file's rows, with their metadata columns, are uploaded as NDJSON into a staging table of their own (`elf_staging_<table>_<id>`, expiring after an hour, dropped after the load).
- One multi-statement transaction then deletes the load's scope and copies the staged rows in, stamping `_loaded_at`, so reloads replace rather than add, as on Postgres, and two concurrent loads of one scope cannot interleave: BigQuery aborts one ("concurrent update"), a retryable 503.
  Its DML bills a few tens of MB from the free 1 TiB of queries a month; every query job is capped at `BQ_MAXIMUM_BYTES_BILLED`, and every job is labelled `component=el-factory` with its purpose, table and run.
- The file sources are not served: BigQuery keeps no `FileLedger`.
- The BigQuery emulator (Compose profile `bigquery`) runs it, except that on some runs a later page's copy finds no staged row there, as if the emulator bound the script's parameters wrong (the same statement alone works); `tests/test_warehouse_bigquery_emulator.py` marks that case, and skips without the emulator unless `PPLK8S_REQUIRE_BIGQUERY=1`.

The tables live in schema `ds_source` and are created with `CREATE TABLE IF NOT EXISTS` for every registered entity at startup (best effort) and again before each extract or load, so dbt sources resolve even before an entity's first extract.
Each extract or load ensures all of them, not only its own: a pipeline's dbt build can read a table another pipeline lands (the weather models are tagged `sales`, PLAN.md D20), and a warehouse reset under a running service (`make services-reset`) would otherwise stay without the tables no request names (#172).
The schema itself must already exist; `warehouse-init` creates it in the Compose stack.
Every table ends with the metadata columns `_run_id text`, `_interval_start timestamptz`, `_interval_end timestamptz`, `_page integer`, `_source_uri text`, and `_loaded_at timestamptz DEFAULT now()`.
All metadata columns except `_loaded_at` are `NOT NULL`.
Each table also has the index `<table>_load_key_idx` on `(_run_id, _interval_start, _interval_end, _page)`.

File entities have their own metadata columns, because a file is keyed by the object it came from rather than by run and interval: `_run_id text`, `_source_uri text`, `_generation bigint`, all `NOT NULL`, plus `_loaded_at timestamptz DEFAULT now()`, and the index `<table>_load_key_idx` on `(_source_uri, _generation)`.

File-source landing tables (`ds_source.tlc_<entity>`) take their data columns from the files themselves (see "Extracting a file source"), followed by `_run_id text`, `_source_uri text`, `_etag text`, `_chunk integer`, all `NOT NULL`, plus `_loaded_at timestamptz DEFAULT now()`, and the index `<table>_chunk_idx` on `(_source_uri, _etag, _chunk)`.
They are created by their first chunk, not at startup.

| Table | Columns |
|---|---|
| `ds_source.synthetic_customers` | `customer_id integer`, `name text`, `email text`, `country text`, `signup_date date` |
| `ds_source.synthetic_orders` | `order_id text`, `customer_id integer`, `order_ts timestamptz`, `status text`, `amount numeric(12,2)`, `currency text` |
| `ds_source.synthetic_campaigns` | `campaign_id integer`, `name text`, `channel text`, `market text`, `start_date date` |
| `ds_source.synthetic_ad_spend` | `spend_date date`, `campaign_id integer`, `impressions integer`, `clicks integer`, `spend numeric(12,2)`, `currency text` |
| `ds_source.synthetic_campaign_budgets` | `snapshot_date date`, `campaign_id integer`, `budget_eur numeric(12,2)`, `remaining_eur numeric(12,2)` |
| `ds_source.synthetic_leads` | `lead_id text`, `campaign_id integer`, `created_ts timestamptz`, `country text` |
| `ds_source.synthetic_bookings` | `booking_id text`, `lead_id text`, `booked_ts timestamptz`, `amount numeric(12,2)`, `currency text` |
| `ds_source.partner_returns` (file entity `partner_returns`) | `return_id text`, `order_id text`, `returned_at timestamptz`, `amount numeric(12,2)`, `reason text` |
| `ds_source.open_meteo_hourly_weather` | `location text`, `latitude numeric(8,4)`, `longitude numeric(8,4)`, `observed_at timestamptz`, `temperature_c numeric(5,2)`, `precipitation_mm numeric(6,2)` |

## Tests

```bash
cd services/el-factory
uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

The unit tests use in-memory fakes for storage and the warehouse and mock the Open-Meteo HTTP call, so they need no network and no services.
The `tlc` tests serve tiny generated Parquet files from a local HTTP server that answers like the TLC CDN (ranges, `ETag`, `If-Match`, both kinds of 403); `tests/test_tlc_extract.py` also needs the Compose warehouse (`make services-up`), writes to a throwaway schema, and skips without it unless `PPLK8S_REQUIRE_WAREHOUSE=1`.

## Image

Its reference is `ELF_IMAGE` in the Makefile, the one place the tag lives (PLAN.md D16).

```bash
make build
docker run --rm "$(make -s print-ELF_IMAGE)" id -u   # prints 10001
```

The image is multi-stage, runs as uid 10001, exposes 8080, and has a `/healthz` health check.
Its build argument `WAREHOUSE` (default `postgres`) names the Dockerfile stage it is built from and sets the image's `ELF_WAREHOUSE`, so the image carries that warehouse's driver only (SL-19).
The `postgres` stage installs the `postgres` and `files` extras and carries the whole package, the file sources included.
The `bigquery` stage (`--build-arg WAREHOUSE=bigquery`, the GCP build, #227) installs `requirements-bigquery.txt`, the `bigquery` extra exported from `uv.lock` (`uv export --frozen --no-default-groups --extra bigquery --no-emit-project -o requirements-bigquery.txt`), and copies the package without `warehouse_postgres.py` and `el_factory/tlc`; its build fails on a Postgres driver, pyarrow or a TLC path, and `make gcp-validate` (`platform/gcp/check_gcp_builds.py`) fails on the same and on a stale export.
Measured on 2026-11-02 (content size, compressed): 107 MB for the `postgres` build, as before the split, and 66 MB for the `bigquery` one.
It runs gunicorn with two workers and the control socket disabled, because that socket is an admin feature the container does not need.
