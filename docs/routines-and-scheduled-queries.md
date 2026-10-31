# Scheduled queries and routines beside dbt

Where BigQuery's scheduled queries and routines (stored procedures, user-defined functions, table functions) fit beside a dbt project, and how a team moves from them to dbt one at a time without defining a calculated field twice ([`semantic/PLAN.md`](../semantic/PLAN.md) U5).
It answers the use case "we have started moving from scheduled queries to stored procedures (routines) and want to do it properly".
"Stated" means read from Google's or dbt's documentation (2026-10); "measured" means run in this repo; "unverified" means neither.

## The short answer

- **Scheduled queries become dbt models**, built by one job in dependency order, the way the lab's dbt job builds a stage after its pipeline extracts.
- **Stored procedures stay only for work dbt cannot express**: administration and procedural logic, never a business number.
- **A user-defined function (UDF) cleans or converts a value in a row**; when it must live in the warehouse, dbt builds it as a function, and a business calculation is never a UDF when a metric covers it.
- **A table function's parameters become a metric query's filters and group-bys**; keep one only for a parameterised read a tool outside dbt needs.
- **Every calculated field lives in exactly one metric** (R1, SL-1), whatever ran it before.

Moving scheduled queries into stored procedures alone keeps the two problems the move is meant to solve: each procedure still runs on its own clock, and each still carries its own copy of the calculation.

## Scheduled queries

**What it is (stated).**
A [scheduled query](https://docs.cloud.google.com/bigquery/docs/scheduling-queries) runs GoogleSQL on a schedule through the BigQuery Data Transfer Service, DDL and DML included.
Each run receives `@run_time` and `@run_date`, writes its result to a destination table by `WRITE_TRUNCATE` (overwrite) or `WRITE_APPEND` (append), and can be run again manually over a range of historical dates.
Each scheduled query has its own schedule; the page describes no way to start one when another finishes, so a chain of them is ordered by clock times.
Runs exactly on the hour may trigger more than once, which duplicates rows an `INSERT` writes; the page advises an off-the-hour time.

**Its dbt counterpart (stated).**
A [model](https://docs.getdbt.com/docs/build/materializations): `WRITE_TRUNCATE` is a `table`; `WRITE_APPEND` or a `@run_date` partition is an `incremental` model.
On BigQuery an [incremental model](https://docs.getdbt.com/reference/resource-configs/bigquery-configs) uses `merge` on a `unique_key` by default, or `insert_overwrite`, which replaces whole partitions; either way a rerun replaces rows instead of appending them twice.
Order comes from `ref()`, not from clock times.
In the lab, each pipeline's DAG runs `dbt build --select tag:<pipeline>,tag:<stage>` as a pod, the dbt job's stand-in, after its extraction lands ([`airflow/include/pplk8s/dbt.py`](../airflow/include/pplk8s/dbt.py)), and a readiness row gates the next pipeline.

**Keep it when:** nothing downstream reads its output, such as an analyst's own export.
Anything a model, a metric, a dashboard or an agent reads moves into dbt.

## Stored procedures

**What it is (stated).**
A [stored procedure](https://docs.cloud.google.com/bigquery/docs/procedures) runs several statements with variables and control flow, takes and returns arguments, and can modify data across datasets; `CALL` runs it.
BigQuery runs each statement in its body as a separate child job, and data access audit log entries are recorded against those child jobs, not the `CALL` job.
As an [authorized routine](https://docs.cloud.google.com/bigquery/docs/authorized-routines), it can create, drop and change tables its caller cannot reach.

**Its dbt counterpart (stated).**
dbt has no procedure resource: its built-in materializations are table, view, incremental, ephemeral and materialized view, and its [functions](https://docs.getdbt.com/docs/build/udfs) cover scalar and aggregate functions only.
A procedure that builds tables splits into models, one per table it writes, joined by `ref()`; its `INSERT` or `MERGE` becomes an incremental model.
Branching on environment or dialect becomes a [macro](https://docs.getdbt.com/docs/build/jinja-macros), resolved when dbt compiles.
A statement that must run around a build goes in an [`on-run-start` or `on-run-end` hook](https://docs.getdbt.com/reference/project-configs/on-run-start-on-run-end), or is run by [`dbt run-operation`](https://docs.getdbt.com/reference/commands/run-operation).
The lab retires old TLC months this way: a macro (`tlc_retire`) that the monthly DAG runs with `dbt run-operation`, where a team without dbt would write a procedure.

**Keep it when** the work is not "write a table from a query": administration (system procedures such as `BQ.REFRESH_MATERIALIZED_VIEW`), a loop whose number of steps depends on the data, or an authorized routine that lets a caller change data they cannot read.
dbt or the orchestrator then calls it, and it computes no business number.
An agent audit (U4) that reads the `CALL` job alone misses the procedure's reads, which sit on its child jobs.

## User-defined functions

**What it is (stated).**
A [UDF](https://docs.cloud.google.com/bigquery/docs/user-defined-functions) wraps a SQL expression or JavaScript code, temporary (one query) or persistent (stored in a dataset).
JavaScript UDFs use more slots than SQL; the page advises SQL whenever the logic can be written in it.
Persistent UDFs cannot change data or call outside systems.
A custom masking routine must be a SQL UDF.
BigQuery also has [user-defined aggregate functions](https://docs.cloud.google.com/bigquery/docs/routines) (`CREATE AGGREGATE FUNCTION`).

**Its dbt counterpart.**
A dbt [function](https://docs.getdbt.com/docs/build/udfs) (dbt 1.11 and later): a SQL, Python or JavaScript body in `functions/` with its arguments and return type in YAML, referenced from a model as `{{ function('name') }}`; dbt creates it in the warehouse before the models that call it, so tools outside dbt can call it too (stated).
The lab's pins (dbt-core 1.12.6, dbt-bigquery 1.12.1) parse such a function into the manifest as a `function` node named `` `pplk8s-lab`.`public`.`<name>` `` and compile it on the offline `bigquery` target (measured, in a scratch copy of `dbt/`; the project defines no function).
Logic only dbt needs is a macro instead: it is compiled into each model's SQL and creates no object in the warehouse (stated).

**Keep it when** the same row-level logic (parsing a code, converting units, masking) must be callable from outside dbt; build it as a dbt function so it is versioned and created with the models.
**Never** for a business calculation: a function that sums revenue, nets returns or divides spend by leads is a second definition beside the metric.
The rule of thumb: a UDF changes one value in one row; a metric aggregates, and only a metric aggregates a business number.

## Table functions

**What it is (stated).**
A [table function](https://docs.cloud.google.com/bigquery/docs/table-functions) is a UDF that returns a table: a view that takes parameters.
Its body must be a single `SELECT`, with no DDL or DML, stored in the same location as the tables it reads.

**Its dbt counterpart.**
The shape becomes a view or table model; the parameters become what a metric query takes: metrics, group-bys, filters and a date range.
That is what MetricFlow and the lab agent's `query_metrics` tool already do (SL-2).
dbt functions do not build table functions (stated: scalar and aggregate only).

**Keep it when** a tool outside dbt needs a parameterised read of rows, such as an application's lookup, and it computes no metric.

## Calculated fields go in metrics

Whatever ran it before, a calculated field is defined once as a [metric](https://docs.getdbt.com/docs/build/metrics-overview) in the semantic YAML, and models keep clean rows and dimensions.
In the lab, net revenue is `net_revenue_eur` in [`dbt/models/semantic/semantic.yml`](../dbt/models/semantic/semantic.yml), and the hand-written gold and exposed tables that compute it too exist only as the parity oracle (SL-1).
A migration that copies a routine's calculation into a model moves the duplication instead of removing it.

## Moving one routine at a time

1. **List what exists.** Scheduled queries are transfer configurations; routines are listed by `INFORMATION_SCHEMA.ROUTINES` ([manage routines](https://docs.cloud.google.com/bigquery/docs/routines), stated).
   For each, write down the tables it writes, who reads them, and the calculated fields it computes.
2. **Pick one** whose output has the fewest readers.
3. **Rebuild it beside the old one.** The dbt model writes to a new dataset, never to the routine's table, and the routine keeps running.
   Each calculated field it computes becomes a metric, or uses the one that already exists.
4. **Compare.** Over the same dates, the new output and the old must match: row counts, keys, and every calculated field within a tolerance agreed before the comparison.
   The lab checks its metrics against the hand-written tables the same way (`make semantic-check`).
5. **Switch readers one at a time**: dashboards, then agents, then automations, each after its own comparison passes.
   Rolling back is pointing that reader at the old table again, which is still current.
6. **Retire the routine** once no reader has used its table for a full cycle: pause the schedule, then delete it.

## Unverified

- Calling a stored procedure from a dbt hook or `dbt run-operation`: hooks run any SQL statement (stated), but no `CALL` was run here.
- Building a dbt function on the BigQuery emulator: the emulator does not support `routines.list` (the shim answers it, SL-7), and nothing here created a function, on the emulator or on Postgres.
- Creating a table function from dbt, through a hook or a macro: not tried.
- Costs and speeds beyond what the pages state (slots for JavaScript UDFs, the overhead of `CALL`): not measured.
