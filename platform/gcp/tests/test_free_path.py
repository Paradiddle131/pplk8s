"""check_free_path.py on the real platform/gcp/ and on copies that stray off the free path."""

from __future__ import annotations

import datetime as dt
import shutil
import sys
from pathlib import Path

import pytest
import yaml

GCP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GCP))

from check_free_path import problems, runs_per_month


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    shutil.copy(GCP / "free-path.yaml", tmp_path)
    shutil.copy(GCP / "workloads.yaml", tmp_path)
    (tmp_path / "infra").mkdir()
    for f in [*(GCP / "infra").glob("*.tf"), *(GCP / "infra").glob("*.yaml")]:
        shutil.copy(f, tmp_path / "infra")
    return tmp_path


def test_the_repo_is_on_the_free_path() -> None:
    assert problems(GCP) == []


def test_a_paid_resource_type_fails(copy: Path) -> None:
    (copy / "infra" / "vm.tf").write_text(
        'resource "google_compute_instance" "vm" {}\n'
    )
    assert any("google_compute_instance" in p for p in problems(copy))


def test_a_paid_api_fails(copy: Path) -> None:
    spec = copy / "free-path.yaml"
    spec.write_text(
        spec.read_text().replace(
            "apis:\n",
            "apis:\n  compute.googleapis.com: {enable: true, source: https://x}\n",
            1,
        )
    )
    assert any("paid list" in p for p in problems(copy))


def test_an_api_named_but_not_enabled_fails(copy: Path) -> None:
    (copy / "infra" / "armor.tf").write_text(
        "# calls https://modelarmor.googleapis.com/v1/projects\n"
    )
    assert any("modelarmor.googleapis.com" in p for p in problems(copy))


def test_a_dated_exception_expires(copy: Path) -> None:
    spec = copy / "free-path.yaml"
    text = spec.read_text().replace(
        "geminidataanalytics.googleapis.com: {enable: false",
        "geminidataanalytics.googleapis.com: {enable: true",
    )
    spec.write_text(text)
    assert problems(copy, dt.date(2026, 12, 1)) == []
    assert any("free window" in p for p in problems(copy, dt.date(2027, 1, 1)))


def test_a_raised_query_cap_fails(copy: Path) -> None:
    spec = copy / "free-path.yaml"
    spec.write_text(
        spec.read_text().replace(
            "bigquery_query_mib_per_day: 31457", "bigquery_query_mib_per_day: 40000"
        )
    )
    assert any("past the free 1 TiB" in p for p in problems(copy))


def test_a_paid_api_cannot_hide_as_implicit(copy: Path) -> None:
    spec = copy / "free-path.yaml"
    spec.write_text(
        spec.read_text().replace(
            "implicit:\n",
            "implicit:\n  compute.googleapis.com: {source: https://x}\n",
            1,
        )
    )
    assert any("cannot be implicit" in p for p in problems(copy))


def test_scanning_is_paid_and_the_registry_turns_it_off() -> None:
    paid = yaml.safe_load((GCP / "free-path.yaml").read_text())["paid"]
    assert {
        "containerscanning.googleapis.com",
        "ondemandscanning.googleapis.com",
    } <= set(paid)
    registry = (GCP / "infra" / "artifact_registry.tf").read_text()
    assert 'enablement_config = "DISABLED"' in registry


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert old in text, f"{old!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1))


@pytest.mark.parametrize(
    ("old", "new", "says"),
    [
        (
            "invoker_iam_disabled = false",
            "invoker_iam_disabled = true",
            "makes a service public",
        ),
        ("cpu_idle          = true", "cpu_idle          = false", "outside requests"),
        ("min_instance_count = 0", "min_instance_count = 1", "idle instances"),
        (
            "max_instance_count = local.caps.cloud_run_max_instances",
            "max_instance_count = 5",
            "above caps.cloud_run_max_instances",
        ),
        ("max_retries     = 0", "max_retries     = 3", "one attempt per run"),
        ("parallelism = 1", "parallelism = 2", "one instance per run"),
    ],
)
def test_a_service_or_job_off_the_free_path_fails(
    copy: Path, old: str, new: str, says: str
) -> None:
    edit(copy / "infra" / "run.tf", old, new)
    assert any(says in p for p in problems(copy))


def test_a_public_invoker_fails(copy: Path) -> None:
    (copy / "infra" / "public.tf").write_text(
        'resource "google_cloud_run_v2_service_iam_member" "open" {\n'
        '  member = "allUsers"\n}\n'
    )
    assert any("public member" in p for p in problems(copy))


def test_a_service_without_its_cap_fails(copy: Path) -> None:
    edit(
        copy / "infra" / "run.tf",
        "      max_instance_count = local.caps.cloud_run_max_instances\n",
        "",
    )
    assert any("without max_instance_count" in p for p in problems(copy))


def test_jobs_past_the_free_vcpu_seconds_fail(copy: Path) -> None:
    # The daily build every hour: 744 runs of 600 s on top of the hourly freshness check.
    edit(copy / "workloads.yaml", 'schedule: "23 4 * * *"', 'schedule: "23 * * * *"')
    assert any("vCPU-seconds" in p for p in problems(copy))


def test_more_scheduled_jobs_than_the_cap_fail(copy: Path) -> None:
    edit(copy / "free-path.yaml", "cloud_scheduler_jobs: 3", "cloud_scheduler_jobs: 1")
    assert any("above caps.cloud_scheduler_jobs" in p for p in problems(copy))


def test_a_scheduler_cap_past_the_free_three_fails(copy: Path) -> None:
    edit(copy / "free-path.yaml", "cloud_scheduler_jobs: 3", "cloud_scheduler_jobs: 4")
    assert any("free jobs" in p for p in problems(copy))


def test_a_second_scheduler_resource_fails(copy: Path) -> None:
    (copy / "infra" / "more.tf").write_text(
        'resource "google_cloud_scheduler_job" "extra" {}\n'
    )
    assert any("one google_cloud_scheduler_job" in p for p in problems(copy))


def test_runs_per_month_is_the_worst_month() -> None:
    assert runs_per_month("17 * * * *") == 744
    assert runs_per_month("23 4 * * *") == 31
    assert runs_per_month("*/15 * * * *") == 2976
    assert runs_per_month("0 9 * * 1-5") == 25
    assert runs_per_month("0 0 1 * 0") == 6
