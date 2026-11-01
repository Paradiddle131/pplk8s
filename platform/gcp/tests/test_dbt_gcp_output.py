"""dbt's `gcp` output (dbt/profiles.yml, #206) against the lab project's caps in free-path.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

GCP = Path(__file__).resolve().parent.parent
DBT = GCP.parent.parent / "dbt"
CAPS = yaml.safe_load((GCP / "free-path.yaml").read_text())["caps"]
OUTPUT = yaml.safe_load((DBT / "profiles.yml").read_text())["pplk8s"]["outputs"]["gcp"]


def test_every_dbt_job_is_capped_at_the_lab_byte_cap() -> None:
    assert OUTPUT["maximum_bytes_billed"] == CAPS["bigquery_maximum_bytes_billed"]
    assert OUTPUT["job_execution_timeout_seconds"] > 0


def test_the_output_reads_the_project_and_runs_where_the_free_tiers_meet() -> None:
    assert OUTPUT["project"] == "{{ env_var('GCP_PROJECT') }}"
    assert OUTPUT["location"] == "US"


def test_dbt_labels_its_jobs() -> None:
    project = yaml.safe_load((DBT / "dbt_project.yml").read_text())
    assert project["query-comment"]["job-label"] is True
