# pplk8s dbt project

This project builds the medallion layers on the lab warehouse (Postgres, the BigQuery stand-in from PLAN.md D8).
It runs on `dbt-core` 1.12.5 with `dbt-postgres` 1.11.0.

## Layers

Each layer is one folder under `models/` and one schema in the warehouse.

| Layer | Schema | Materialization | Content |
|---|---|---|---|
| bronze | `bronze` | view | 1:1 with the `ds_source` landing tables; cast only, keeps every run and the metadata columns; `partner_returns`, `tlc_yellow_trips`, `tlc_green_trips`, and the `tlc_taxi_zones` seed |
| silver | `silver` | table, or incremental per data month (`tlc`) | Latest row per natural key (`_loaded_at`, then `_run_id` or `_generation`, decides the winner); `customers`, `orders`, `hourly_weather`, `returns`, `tlc_trips`, `tlc_trips_quarantine` |
| gold | `gold` | table, or incremental per data month (`tlc`) | `daily_sales`, `customer_lifetime`, `daily_weather`, `tlc_daily_trips` |
| exposed | `exposed` | view, or table when it reads another pipeline | `sales_by_country_daily`, `daily_sales_with_weather`, `tlc_daily_trips_by_borough` (views), `net_sales_daily` (table) |

Model names carry a layer prefix (`brz_`, `slv_`, `gld_`, `exp_`) so they stay unique across the project; the `alias` config gives the clean table name.
Bronze reads `ds_source` through `source()`.

## Selecting a stage

Every layer has a tag and a selector with the same name.
These two commands select the same models:

```
dbt build --select bronze
dbt build --selector bronze
```

`--select <layer>` matches the folder, and `--selector <layer>` matches the tag.
Tests follow their models; the gold reconciliation test lives in `tests/gold/` and carries the `gold` tag.

The project sets `indirect_selection: cautious` in `dbt_project.yml`.
A test runs only when all of its parents are selected, so `build --select silver` does not run tests that need gold.

Run the stages in order: bronze, silver, gold, exposed.
Each stage reads tables built by the stage before it.

## Selecting a pipeline's stage

Every model also carries the tag of the pipeline that owns it (PLAN.md D20), set in its `config()` next to the alias:

| Pipeline | DAG | Models |
|---|---|---|
| `sales` | `sales_elt` | every customers, orders, and weather model, and the gold reconciliation test |
| `returns` | `returns_file_arrival` | `brz_partner_returns`, `slv_returns` |
| `finance` | `finance_daily` | `exp_net_sales_daily` (reads `sales` gold and `returns` silver) |
| `tlc` | `tlc_monthly` | every `tlc` model, the `tlc_taxi_zones` seed, and the tlc reconciliation tests |

Airflow's `run_dbt` builds the intersection of the two tags, so one pipeline's stage never rebuilds another pipeline's models:

```
dbt build --select tag:returns,tag:silver
```

The weather models stay in `sales` because `sales_elt` builds them today; they move to their own tag when a weather DAG exists.

A model that reads another pipeline's model is a table, never a view.
dbt-postgres rebuilds a relation by dropping the old one with `CASCADE`, which drops every view that depends on it, so a view on another pipeline's model would disappear whenever that pipeline rebuilds its stage (issue #27).
The image build runs `scripts/check_pipeline_views.py` on the parsed manifest and fails on such a view.

## The tlc models: one data month per build

The NYC TLC models (PLAN.md D34-D36) replace one data month at a time.
`tlc_monthly` passes the month as a var, and these models build only that month:

```
dbt build --select tag:tlc,tag:silver --vars '{data_month: 2026-08}'
```

Without `data_month`, every landed month is built; a value other than `YYYY-MM` fails compilation.

- Bronze (`macros/tlc.sql`, `tlc_bronze`): one view per trip type maps the landed columns to one canonical set (`tlc_columns()`), and fills NULL for any column the landing table has never seen (a column a later month added, or one the trip type does not publish).
  It reads the landing table's columns when it is built, so a column EL Factory adds appears after the next bronze build; a landing table that does not exist yet gives an empty view.
  Green's own `trip_type` column (street hail or dispatch) becomes `hail_type`, so that `trip_type` can say `yellow` or `green`.
- Silver: `tlc_trips` and `tlc_trips_quarantine` read only the latest completed file version of each month (`ops.file_versions`), so a version that is still loading stays invisible.
  Both are `incremental` with `delete+insert` on `data_month`, so a build swaps whole months: a republished file (a new `etag`) replaces its month, and a rebuild never duplicates rows.
  A row breaks at most one rule, the first that fails: `negative_amount`, `pickup_outside_month`, `dropoff_before_pickup`, `over_24_hours`.
  The `quarantine_share` test warns above 2 % of a month quarantined and fails above 10 %.
- Reconciliation: `tests/silver/assert_tlc_bronze_equals_silver_plus_quarantine.sql` checks bronze = silver + quarantine for each month, and `tests/gold/assert_tlc_gold_trips_match_silver.sql` checks gold against silver.
- Retention (`macros/tlc.sql`, `tlc_retire`, PLAN.md D35): `dbt run-operation tlc_retire --args "{keep: '2023-01,2026-08'}"` deletes every month not in `keep` from silver, quarantine and gold; bronze and exposed are views and follow.
  `tlc_monthly` runs it before each load with the months it keeps; an empty `keep` fails, a table not built yet is skipped, and a repeat deletes nothing.
- Zones: `seeds/bronze/tlc_taxi_zones.csv` is TLC's `taxi_zone_lookup.csv` with a snake_case header.
  Seeds sit in a layer folder, so `--select bronze` builds them together with that layer's models.

## Environment variables

The connection is set in `profiles.yml`, and every value is read from the environment with a default.

| Variable | Default | Purpose |
|---|---|---|
| `DBT_HOST` | `warehouse` | Postgres host (the Compose service name on the `pplk8s` network) |
| `DBT_PORT` | `5432` | Postgres port |
| `DBT_USER` | `warehouse` | Database user |
| `DBT_PASSWORD` | `warehouse` | Database password (lab-only default) |
| `DBT_DBNAME` | `warehouse` | Database name; development uses `dbt_dev` |
| `DBT_SCHEMA` | `public` | Target schema for models without a custom schema; the layer models always use their own schema |

## Image

Build the image from the repository root; its reference is `DBT_IMAGE` in the Makefile, the one place the tag lives (PLAN.md D16):

```
make build
```

Run a stage against the lab warehouse:

```
make dbt-build STAGE=bronze
```

The image's entrypoint is `dbt` and its default command is `build`.
It runs as uid 10001.
`dbt parse` runs at build time as a smoke check that needs no database.

## Development fixture

`dev/fixture.sql` is dev-only.
It creates the four `ds_source` tables with the contract DDL and loads synthetic rows.
Load it into a scratch database, never into `warehouse`:

```
docker exec -i pplk8s-warehouse-1 psql -U warehouse -d dbt_dev -v ON_ERROR_STOP=1 < dbt/dev/fixture.sql
```

Create the scratch database first if the warehouse volume is new: `docker exec pplk8s-warehouse-1 createdb -U warehouse dbt_dev`.

`dev/tlc_fixture.sql` is the tlc counterpart.
It holds two months of yellow and green rows in the D34 landing contract, a half-loaded second file version, and one row per quarantine rule.
`dev/tlc_republish.sql` then completes that second version.
`tests/e2e/tlc-dbt-check.sh` loads both into `dbt_dev` and builds the months with host dbt (`uvx`, the image's pins).
It checks that rebuilding one month leaves the other untouched, that the reconciliation holds, that a republished month replaces the old one, and that a month above 10 % quarantined fails the build.

## Dialect notes

Models use only portable SQL except where a line carries a `-- dialect:` comment.
The Postgres-specific spots are the `AT TIME ZONE 'UTC'` date casts in `slv_orders`, `slv_returns`, and `gld_daily_weather`, and in `macros/tlc.sql` the file-name regex (`substring ... from`) and the `double precision`/`timestamp` types.
On BigQuery, the tlc incremental models would use `insert_overwrite` on a month-partitioned `pickup_date` (D36).
