"""Copy the dev fixture's landed sources from Postgres into a BigQuery (semantic/PLAN.md SL-7, #206), so
`dbt build` there starts from the same rows as `dbt_dev`: the emulator, or the lab project on real BigQuery
(tests/e2e/lib/bigquery_target.py picks it from BQ_API_ENDPOINT).

Usage: fixture_to_bigquery.py <postgres dsn>
The BigQuery is left holding only the fixture's sources, as a fresh emulator would: every table in the
datasets dbt builds into is deleted first (never `ops`, which keeps the agents' audit, nor the datasets
themselves); then each source table is written with BigQuery types mapped from Postgres's. The emulator
gets its datasets created here (it creates none on `create schema`); on the lab project they are OpenTofu's
(platform/gcp/infra/bigquery.tf), so a missing one fails with what to run.
"""

import datetime
import decimal
import sys
from pathlib import Path

import psycopg
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

# `python -I` leaves the script's own folder off sys.path; the target helper sits beside it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bigquery_target import client, endpoint, load_rows  # noqa: E402

# The tables the semantic path reads; tlc stays Postgres-only (its models are marked `-- dialect:`).
SOURCES = (
    "synthetic_customers",
    "synthetic_orders",
    "partner_returns",
    "open_meteo_hourly_weather",
    "synthetic_campaigns",
    "synthetic_ad_spend",
    "synthetic_campaign_budgets",
    "synthetic_leads",
    "synthetic_bookings",
    "synthetic_customer_actions",
    "synthetic_partners",
    "synthetic_partner_contacts",
    "synthetic_outreach_messages",
    "synthetic_outreach_replies",
    "synthetic_applications",
    "synthetic_call_transcripts",
)
# ops: the agent's audit table (macros/agent_warehouse.sql); the emulator takes `create schema` but creates nothing.
DATASETS = ("ds_source", "bronze", "silver", "gold", "exposed", "semantic", "legacy", "migration", "ops")
# Emptied before the copy: what a build reads or writes, never the audit (`ops`).
EMPTIED = tuple(d for d in DATASETS if d != "ops")
TYPES = {
    "text": "STRING",
    "integer": "INT64",
    "bigint": "INT64",
    "numeric": "NUMERIC",
    "double precision": "FLOAT64",
    "date": "DATE",
    "timestamp with time zone": "TIMESTAMP",
    "timestamp without time zone": "DATETIME",
    "boolean": "BOOL",
}


def to_json(value):
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, datetime.datetime):
        if value.tzinfo is not None:
            value = value.astimezone(datetime.UTC)
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value


def main(dsn: str) -> None:
    bq = client()
    for dataset in DATASETS:
        if endpoint():
            bq.create_dataset(f"{bq.project}.{dataset}", exists_ok=True)
            continue
        try:
            bq.get_dataset(f"{bq.project}.{dataset}")
        except NotFound:
            sys.exit(f"dataset {bq.project}.{dataset} is missing: the owner's `make gcp-up` creates the lab's datasets")
    for dataset in EMPTIED:
        for table in bq.list_tables(f"{bq.project}.{dataset}"):
            bq.delete_table(table, not_found_ok=True)
    with psycopg.connect(dsn) as conn:
        for name in SOURCES:
            columns = conn.execute(
                "select column_name, data_type from information_schema.columns"
                " where table_schema = 'ds_source' and table_name = %s order by ordinal_position",
                (name,),
            ).fetchall()
            if not columns:
                sys.exit(f"ds_source.{name} is missing: load dbt/dev/fixture.sql first")
            schema = [bigquery.SchemaField(column, TYPES[kind]) for column, kind in columns]
            rows = [
                {column: to_json(value) for (column, _), value in zip(columns, row, strict=True)}
                for row in conn.execute(f'select * from ds_source."{name}"')
            ]
            load_rows(bq, f"ds_source.{name}", rows, schema)
            print(f"ds_source.{name}: {len(rows)} rows")


if __name__ == "__main__":
    main(sys.argv[1])
