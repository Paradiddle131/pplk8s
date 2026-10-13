-- Datasets of the warehouse stand-in (PLAN.md D8).
CREATE SCHEMA IF NOT EXISTS ds_stage;
CREATE SCHEMA IF NOT EXISTS ds_source;
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS exposed;
CREATE SCHEMA IF NOT EXISTS ops;

-- Readiness ledger (PLAN.md §3); written by DAGs from Phase 4 on.
CREATE TABLE IF NOT EXISTS ops.readiness (
  product        text        NOT NULL,
  interval_start timestamptz NOT NULL,
  interval_end   timestamptz NOT NULL,
  watermark      timestamptz,
  run_id         text        NOT NULL,
  status         text        NOT NULL,
  updated_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (product, interval_start, interval_end)
);
-- The Airflow DAG whose run `run_id` wrote the row (PLAN.md D32); NULL for any other producer.
-- Run ids are unique per DAG only, so (dag_id, run_id) is what ties a row to Airflow's history.
ALTER TABLE ops.readiness ADD COLUMN IF NOT EXISTS dag_id text;

-- File-load ledger (PLAN.md D18): one row per landed object generation a file-arrival DAG loaded.
-- Survives Airflow's own metadata (db clean, deleted runs), so a redelivered event is a no-op.
CREATE TABLE IF NOT EXISTS ops.file_loads (
  bucket     text        NOT NULL,
  object     text        NOT NULL,
  generation bigint      NOT NULL,
  entity     text        NOT NULL,
  run_id     text        NOT NULL,
  rows       integer     NOT NULL,
  loaded_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (bucket, object, generation)
);

-- File-source chunk ledger (PLAN.md D34): one row per chunk (Parquet row group) of one file version
-- that EL Factory loaded into ds_source; a request resumes after the chunks recorded for the
-- file's current etag. EL Factory drops the rows of older versions when a newer one completes.
CREATE TABLE IF NOT EXISTS ops.file_chunks (
  source_uri text        NOT NULL,
  etag       text        NOT NULL,
  chunk      integer     NOT NULL,
  rows       bigint      NOT NULL,
  loaded_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (source_uri, etag, chunk)
);

-- Completed file versions (PLAN.md D34, D36): written with the last chunk; silver reads only the
-- latest completed (source_uri, etag) of a month, so a half-loaded version stays invisible.
CREATE TABLE IF NOT EXISTS ops.file_versions (
  source_uri   text        NOT NULL,
  etag         text        NOT NULL,
  completed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (source_uri, etag)
);
