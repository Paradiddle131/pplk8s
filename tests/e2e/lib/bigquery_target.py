"""The BigQuery that tests/e2e/bigquery-run-check.sh runs the semantic path on: the emulator or the lab project.

BQ_API_ENDPOINT set: the emulator there (semantic/PLAN.md SL-7), project `pplk8s-lab`, no credentials.
Unset: real BigQuery on the lab project GCP_PROJECT (SL-13), with application default credentials, or the
access token in GCP_ACCESS_TOKEN where a proxy injects the real one; every query this client runs is capped
at BQ_MAXIMUM_BYTES_BILLED bytes (default 1 GiB, as dbt's `gcp` output).
"""

from __future__ import annotations

import datetime
import os
import sys

from google.cloud import bigquery

EMULATOR_PROJECT = "pplk8s-lab"
DEFAULT_CAP = 1073741824


def endpoint() -> str:
    return os.environ.get("BQ_API_ENDPOINT", "")


def project() -> str:
    if endpoint():
        return EMULATOR_PROJECT
    if not os.environ.get("GCP_PROJECT"):
        sys.exit("GCP_PROJECT is unset: the live BigQuery run needs the lab project's id (platform/gcp/README.md)")
    return os.environ["GCP_PROJECT"]


def client() -> bigquery.Client:
    if endpoint():
        from google.api_core.client_options import ClientOptions
        from google.auth.credentials import AnonymousCredentials

        return bigquery.Client(
            project=EMULATOR_PROJECT,
            credentials=AnonymousCredentials(),
            client_options=ClientOptions(api_endpoint=endpoint()),
        )
    if token := os.environ.get("GCP_ACCESS_TOKEN"):
        import google.oauth2.credentials

        credentials = google.oauth2.credentials.Credentials(token)
    else:
        import google.auth

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    cap = int(os.environ.get("BQ_MAXIMUM_BYTES_BILLED", DEFAULT_CAP))
    return bigquery.Client(
        project=project(),
        credentials=credentials,
        location="US",
        default_query_job_config=bigquery.QueryJobConfig(maximum_bytes_billed=cap),
    )


def load_rows(
    bq: bigquery.Client, table: str, rows: list[dict], schema: list[bigquery.SchemaField], *, append: bool = False
) -> None:
    """Write JSON rows into `dataset.table`, replacing it unless `append`.

    On BigQuery a load job, which is free, where a streaming insert is not (platform/gcp/README.md); the emulator
    hangs on a JSON load job's upload, so there the table is created and the rows streamed, which costs nothing.
    """
    ref = f"{bq.project}.{table}"
    if endpoint():
        if not append:
            bq.delete_table(ref, not_found_ok=True)
            bq.create_table(bigquery.Table(ref, schema))
        if rows and (errors := bq.insert_rows_json(ref, rows)):
            sys.exit(f"{table}: {errors[:3]}")
        return
    config = bigquery.LoadJobConfig(
        schema=schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition="WRITE_APPEND" if append else "WRITE_TRUNCATE",
    )
    bq.load_table_from_json(rows, ref, job_config=config).result()


def bytes_billed_since(bq: bigquery.Client, since: datetime.datetime) -> int | None:
    """The bytes billed by this credential's jobs created since `since`; None on the emulator, which bills nothing."""
    if endpoint():
        return None
    return sum(getattr(job, "total_bytes_billed", None) or 0 for job in bq.list_jobs(min_creation_time=since))


if __name__ == "__main__":
    # `bigquery_target.py bytes-billed-since <ISO timestamp>`: the run's bytes billed, for the check's summary.
    if sys.argv[1:2] != ["bytes-billed-since"] or len(sys.argv) != 3:
        sys.exit("usage: bigquery_target.py bytes-billed-since <ISO timestamp>")
    billed = bytes_billed_since(client(), datetime.datetime.fromisoformat(sys.argv[2]))
    print("n/a" if billed is None else billed)
