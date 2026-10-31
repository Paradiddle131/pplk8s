"""Copy the dev fixture's landed sources from Postgres into the BigQuery emulator (semantic/PLAN.md
SL-7), so `dbt build` on the `bigquery_emulator` target starts from the same rows as `dbt_dev`.

Usage: fixture_to_bigquery.py <postgres dsn> <bigquery api endpoint> <project>
It creates every dataset the project builds into, then each source table with BigQuery types
mapped from Postgres's, and inserts its rows. The emulator must be empty (it runs in memory).
"""

import datetime
import decimal
import sys

import psycopg
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

# The tables the semantic path reads; tlc stays Postgres-only (its models are marked `-- dialect:`).
SOURCES = (
    "synthetic_customers",
    "synthetic_orders",
    "partner_returns",
    "open_meteo_hourly_weather",
    "synthetic_campaigns",
    "synthetic_ad_spend",
    "synthetic_leads",
    "synthetic_bookings",
)
# ops: the agent's audit table (macros/agent_warehouse.sql); the emulator takes `create schema` but creates nothing.
DATASETS = ("ds_source", "bronze", "silver", "gold", "exposed", "semantic", "legacy", "migration", "ops")
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


def main(dsn: str, endpoint: str, project: str) -> None:
    client = bigquery.Client(
        project=project,
        credentials=AnonymousCredentials(),
        client_options=ClientOptions(api_endpoint=endpoint),
    )
    for dataset in DATASETS:
        client.create_dataset(f"{project}.{dataset}", exists_ok=True)
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
            table = client.create_table(bigquery.Table(f"{project}.ds_source.{name}", schema))
            rows = [
                {column: to_json(value) for (column, _), value in zip(columns, row, strict=True)}
                for row in conn.execute(f'select * from ds_source."{name}"')
            ]
            if errors := client.insert_rows_json(table, rows):
                sys.exit(f"ds_source.{name}: {errors[:3]}")
            print(f"ds_source.{name}: {len(rows)} rows")


if __name__ == "__main__":
    main(*sys.argv[1:4])
