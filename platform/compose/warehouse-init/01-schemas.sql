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
