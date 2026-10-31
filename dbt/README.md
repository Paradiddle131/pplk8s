# pplk8s dbt project

This project builds the medallion layers on the lab warehouse (Postgres, the BigQuery stand-in from PLAN.md D8).
It runs on `dbt-core` 1.12.6 with `dbt-postgres` 1.11.0, and carries the semantic layer on `dbt-metricflow[dbt-postgres]` 0.15.0 ([`semantic/PLAN.md`](../semantic/PLAN.md)).

## Layers

Each layer is one folder under `models/` and one schema in the warehouse.

| Layer | Schema | Materialization | Content |
|---|---|---|---|
| bronze | `bronze` | view | 1:1 with the `ds_source` landing tables; cast only, keeps every run and the metadata columns; `partner_returns`, `tlc_yellow_trips`, `tlc_green_trips`, and the `tlc_taxi_zones` seed |
| silver | `silver` | table, or incremental per data month (`tlc`) | Latest row per natural key (`_loaded_at`, then `_run_id` or `_generation`, decides the winner); `customers`, `orders`, `hourly_weather`, `returns`, `campaigns`, `ad_spend`, `leads`, `bookings`, `tlc_trips`, `tlc_trips_quarantine` |
| gold | `gold` | table, or incremental per data month (`tlc`) | `daily_sales`, `customer_lifetime`, `daily_weather`, `marketing_daily`, `tlc_daily_trips` |
| exposed | `exposed` | view, or table when it reads another pipeline | `sales_by_country_daily`, `daily_sales_with_weather`, `channel_performance_daily`, `tlc_daily_trips_by_borough` (views), `net_sales_daily` (table) |
| semantic | `semantic` | table | MetricFlow's `time_spine`, and `metrics`, one row per metric; the semantic models and metrics live in the manifest |

Model names carry a layer prefix (`brz_`, `slv_`, `gld_`, `exp_`) so they stay unique across the project; the `alias` config gives the clean table name.
The [agent-ready standard](../docs/agent-ready-warehouse.md) holds the naming, description and contract rules, and `scripts/check_standard.py` enforces them on every parse.
Gold and exposed enforce model contracts: every column declares its `data_type` in `schema.yml`, and a model whose SQL renames, drops, adds or retypes one fails `dbt build`.
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
| `marketing` | `marketing_elt` | every campaigns, ad spend, leads and bookings model: `gld_marketing_daily`, `exp_channel_performance_daily` (PLAN.md D38) |
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

## The semantic layer

The semantic layer is written in dbt's [latest YAML spec](https://docs.getdbt.com/docs/build/latest-metrics-spec) (semantic/PLAN.md SL-1).
A silver model in `models/silver/schema.yml` becomes a MetricFlow semantic model through its `semantic_model` key (`orders` over `slv_orders`, `returns`, `campaigns`, `ad_spend`, `leads`, `bookings`); its columns carry the entities and dimensions, and its `metrics` the simple metrics and the ratios within it.
`customers` and `campaigns` carry no metric of their own: their entity lets the metrics of the models that reference it group and filter by their dimensions (`customer__country`, `customer__signup_date__month` for signup cohorts, `campaign__channel`).
`models/semantic/semantic.yml` holds the metrics that combine semantic models (`net_revenue_eur`, `cost_per_lead_eur`, `cost_per_booking_eur`, `lead_to_booking_rate`).
Each calculated field of the gold and exposed models is defined once, as a metric; the hand-written tables stay as the parity oracle.
No metric sets `fill_nulls_with`, because dbt-core 1.12.6 drops it in this spec: a simple metric reads NULL, not 0, in a day or group where it has no rows, and `net_revenue_eur` coalesces its inputs.
`metricflow_time_spine.sql` is the daily time spine (`semantic.time_spine`), tagged `sales` because the sales build owns it; `semantic_metrics.sql` (`semantic.metrics`) and `semantic_glossary.sql` (`semantic.glossary`) are tagged `sales` with it.

Business terms that are not metrics (`Signup cohort`, `Channel`, `Market`, `Conversion`) are a glossary in `config.meta.glossary` on the silver model that holds the concept: each term has a description, synonyms, and the metrics and dimensions it maps to.
A term never repeats a metric: the metric's label and description are already its glossary entry.

Every metric and semantic model carries a `description`, and every metric a `label`: they become the agent catalog and the warehouse comments, so `scripts/check_standard.py` fails the parse step without them.
It checks the whole [agent-ready standard](../docs/agent-ready-warehouse.md): naming by layer, which models are public with a typed contract, and the descriptions agents read.

The stage check runs with host dbt on the image's pins, against the Compose warehouse (`DBT_DBNAME=warehouse` by default, `dbt_dev` for the fixture):

```
make dbt-validate DBT_DBNAME=dbt_dev
```

It parses the project, runs `check_standard.py`, and runs `mf validate-configs`, which checks the semantic models, dimensions, entities and metrics against the warehouse's tables.
The image build runs the offline half (`mf validate-configs --skip-dw`) beside `dbt parse`.
In the cluster, `finance_daily` runs the whole check after its exposed stage (`validate_semantic_layer` in the workload seam: `dbt parse`, then `mf validate-configs`, in one pod of this image).

Query a metric with the `mf` CLI from this folder, with the same environment:

```
uvx --with-requirements requirements.txt --from dbt-metricflow mf query --metrics net_revenue_eur --group-by metric_time__day
```

`tests/e2e/semantic-check.sh` (`make semantic-check`) builds the sales, returns, finance and marketing models on `dev/fixture.sql` in `dbt_dev`, runs `make dbt-validate` on it, loads the metric queries back into the warehouse and asserts they equal the gold and exposed models row for row (a missing count or sum as 0), and checks that an undescribed metric and an unprefixed, undescribed gold model fail the validation.

### Trust tiers and the catalog

Gold and exposed models are `access: public` in the `analytics` group (`models/groups.yml`): the tables agents and people may read (semantic/PLAN.md SL-4).
Bronze, silver and the semantic stage are `protected` and stay out of the agent catalog; the metrics read silver through the semantic models, so an agent reaches silver only through a metric.
Every public model and every one of its columns carries a `description`, and `persist_docs` writes them to the warehouse as table and column comments (BigQuery descriptions on a BigQuery target) whenever the model builds.

Naming: a metric is the quantity in snake case with its unit as a suffix (`revenue_eur`, `net_revenue_eur`), a count names what it counts and how (`orders_total`, `orders_cancelled`, `customers_distinct`), and its `label` is the business term in plain words with the unit in brackets (`Net revenue (EUR)`).
A dimension is addressed as `<entity>__<dimension>` (`order__status`), and time as `metric_time__day` (or `__week`, `__month`, `__year`).

`make dbt-catalog` (`DBT_DBNAME=warehouse|dbt_dev`) parses the project, runs `scripts/build_catalog.py`, then `scripts/check_catalog.py`, then builds the semantic stage.
The generator reads `target/manifest.json` and `target/semantic_manifest.json` and asks MetricFlow, offline, for each metric's dimensions and compiled SQL; it writes, under `target/catalog/`:

| Artefact | For | Holds |
|---|---|---|
| `agent.json` | the semantic agent's metric tools (S3) | public models (relation, layer, pipelines, grain, columns), metrics (label, description, type, pipelines, time grain, dimensions) and the glossary (term, description, synonyms, metrics, dimensions, the model that defines it) |
| `data_agent/system_instruction.yaml` | a BigQuery data agent's authored context | `system_instruction`, `tables` with fields and aggregations from the simple metrics, `relationships` from the entities, `glossaries` from the metrics and the glossary terms (whose description names their metrics and dimensions), `additional_descriptions` from the derived and ratio formulas, in Google's documented form |
| `data_agent/example_queries.json` | the data agent's verified queries | one `naturalLanguageQuestion` and `sqlQuery` per metric: the metric by day, as MetricFlow compiles it |

The third artefact lives in the warehouse: the gold and exposed comments, `semantic.metrics` and `semantic.glossary` (`models/semantic/`), rendered from dbt's graph at build time.
Table names are `database.schema.table` of the dbt target, so a BigQuery target gives `project.dataset.table` and BigQuery SQL with no change to the generator.
`check_catalog.py` fails when the catalog misses a public model, a metric or a glossary term, when a public model or column has no description, when the authored context strays from the documented keys, or when a glossary term has no description, maps to nothing, names a metric the semantic manifest lacks or a dimension none of its metrics groups by, or repeats a metric or another term.

`tests/e2e/catalog-check.sh` (`make catalog-check`) builds every public model on both dev fixtures in `dbt_dev`, runs `make dbt-catalog`, and asserts that every gold and exposed relation and column has a comment, that `semantic.metrics` holds every metric and `semantic.glossary` every term, that every example query runs, and that an undocumented key, an undescribed column or a stray glossary term fails the check.

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
| `DBT_TARGET` | `dev` | The profile output: `dev` (Postgres), or `bigquery`, compile-only (below) |
| `BQ_PROJECT`, `BQ_LOCATION` | `pplk8s-lab`, `EU` | The `bigquery` target's project and location |

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

## Dialect

The sales, returns, finance and semantic models compile on Postgres and BigQuery unchanged.
Each construct the two spell differently is a dispatch macro in `macros/dialect.sql` (`utc_date`, `day_spine`, `type_timestamptz`), or dbt's own `dbt.type_string()`.
The tlc models keep Postgres forms, each marked with a `-- dialect:` comment: the file-name regex (`substring ... from`), the `double precision`/`timestamp` types, and on BigQuery `insert_overwrite` on a month-partitioned `pickup_date` instead of `delete+insert` (D36).

`profiles.yml` has a compile-only `bigquery` output (`DBT_TARGET=bigquery`).
Its placeholder `oauth-secrets` token lets dbt build a client offline; nothing runs against GCP.
`make bigquery-check` parses, validates and compiles the semantic path on it, checks that the compiled SQL is BigQuery's, and writes the BigQuery catalog to `target/bigquery/catalog` ([the mapping](../docs/semantic-layer-on-bigquery.md)).
