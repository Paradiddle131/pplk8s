# pplk8s dbt project

This project builds the medallion layers on the lab warehouse (Postgres, the BigQuery stand-in from PLAN.md D8).
It runs on `dbt-core` 1.12.5 with `dbt-postgres` 1.11.0.

## Layers

Each layer is one folder under `models/` and one schema in the warehouse.

| Layer | Schema | Materialization | Content |
|---|---|---|---|
| bronze | `bronze` | view | 1:1 with the `ds_source` landing tables; cast only, keeps every run and the metadata columns; `partner_returns` |
| silver | `silver` | table | Latest row per natural key (`_loaded_at`, then `_run_id` or `_generation`, decides the winner); `customers`, `orders`, `hourly_weather`, `returns` |
| gold | `gold` | table | `daily_sales`, `customer_lifetime`, `daily_weather` |
| exposed | `exposed` | view | `sales_by_country_daily`, `daily_sales_with_weather`, `net_sales_daily` |

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

Airflow's `run_dbt` builds the intersection of the two tags, so one pipeline's stage never rebuilds another pipeline's models:

```
dbt build --select tag:returns,tag:silver
```

The weather models stay in `sales` because `sales_elt` builds them today; they move to their own tag when a weather DAG exists.

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

## Dialect notes

Models use only portable SQL except where a line carries a `-- dialect:` comment.
The Postgres-specific spots are the `AT TIME ZONE 'UTC'` date casts in `slv_orders`, `slv_returns`, and `gld_daily_weather`.
