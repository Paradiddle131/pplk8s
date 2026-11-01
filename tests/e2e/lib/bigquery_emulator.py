"""Read the BigQuery emulator for the demo (docs/demo.md): the layers' tables, a table's columns, one query.

Usage: python bigquery_emulator.py ENDPOINT tables
       python bigquery_emulator.py ENDPOINT columns DATASET.TABLE
       python bigquery_emulator.py ENDPOINT sql 'SELECT ...'
Prints tab-separated rows; the project is the emulator's `pplk8s-lab`, which needs no credentials.
"""

from __future__ import annotations

import sys

from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

PROJECT = "pplk8s-lab"
LAYERS = ("bronze", "silver", "gold", "exposed", "semantic", "legacy", "migration", "ops")


def client(endpoint: str) -> bigquery.Client:
    return bigquery.Client(
        project=PROJECT, credentials=AnonymousCredentials(), client_options=ClientOptions(api_endpoint=endpoint)
    )


def tables(bq: bigquery.Client) -> list[str]:
    """One line per layer dataset: its name, its table count, its tables."""
    found = {d.dataset_id for d in bq.list_datasets()}
    lines = []
    for layer in (layer for layer in LAYERS if layer in found):
        names = sorted(t.table_id for t in bq.list_tables(f"{PROJECT}.{layer}"))
        lines.append(f"{layer}\t{len(names)}\t{', '.join(names)}")
    return lines


def columns(bq: bigquery.Client, table: str) -> list[str]:
    """The table's description, then one line per column: name, type, description."""
    t = bq.get_table(f"{PROJECT}.{table}")
    return [f"{table}\t\t{t.description or ''}"] + [
        f"{c.name}\t{c.field_type}\t{c.description or ''}" for c in t.schema
    ]


def sql(bq: bigquery.Client, query: str) -> list[str]:
    result = bq.query(query).result()
    header = "\t".join(f.name for f in result.schema)
    return [header] + ["\t".join("" if v is None else str(v) for v in row.values()) for row in result]


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("tables", "columns", "sql") or (argv[1] != "tables") != (len(argv) == 3):
        print(__doc__, file=sys.stderr)
        return 2
    bq = client(argv[0])
    lines = tables(bq) if argv[1] == "tables" else columns(bq, argv[2]) if argv[1] == "columns" else sql(bq, argv[2])
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
