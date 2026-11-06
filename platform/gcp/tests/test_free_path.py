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


def with_daily_fence(copy: Path, mib: int) -> Path:
    spec = copy / "free-path.yaml"
    spec.write_text(
        spec.read_text().replace(
            "bigquery_query_mib_per_day: 209715", f"bigquery_query_mib_per_day: {mib}"
        )
    )
    return copy


def test_the_owners_daily_fence_is_a_per_day_brake(copy: Path) -> None:
    # The owner's 0.2 TiB a day (#370) is past 1 TiB over 31 days, which the old rule refused; the month's TiB is
    # the limit, held by the usage gate at half of it, and one day's fence fits in the other half.
    assert 209715 * 31 > 1024 * 1024
    assert problems(copy) == []
    assert problems(with_daily_fence(copy, 512 * 1024)) == []


def test_a_daily_fence_past_half_the_free_tib_fails(copy: Path) -> None:
    found = problems(with_daily_fence(copy, 512 * 1024 + 1))
    assert any("past the free 1 TiB" in p for p in found)


def test_a_missing_daily_fence_fails(copy: Path) -> None:
    found = problems(with_daily_fence(copy, 0))
    assert any("bigquery_query_mib_per_day: missing" in p for p in found)


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


def test_the_alerting_policy_expires_before_monitoring_charges_for_it(
    copy: Path,
) -> None:
    # Cloud Monitoring charges for alerting "no sooner than September 1, 2027".
    assert problems(copy, dt.date(2027, 8, 31)) == []
    assert any(
        "google_monitoring_alert_policy declared past its free window" in p
        for p in problems(copy, dt.date(2027, 9, 1))
    )


def test_a_paid_notification_channel_fails(copy: Path) -> None:
    edit(
        copy / "infra" / "monitoring.tf",
        'type         = "email"',
        'type         = "sms"',
    )
    assert any("notification channel of type sms" in p for p in problems(copy))


def test_a_second_log_based_metric_fails(copy: Path) -> None:
    (copy / "infra" / "more.tf").write_text(
        'resource "google_logging_metric" "another" {}\n'
    )
    assert any("one google_logging_metric" in p for p in problems(copy))


def test_log_metric_series_past_the_free_bytes_fail(copy: Path) -> None:
    # 500 series x 44,640 points x 8 bytes = 170 MiB, past the free 150 MiB.
    edit(copy / "free-path.yaml", "log_metric_series: 100", "log_metric_series: 500")
    assert any("free 150 MiB" in p for p in problems(copy))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("unit: milli_vcpu, value: 4000}", "unit: milli_vcpu, value: 4001}"),
        ("unit: bytes, value: 2147483648}", "unit: bytes, value: 4294967296}"),
    ],
)
def test_a_cloud_run_quota_above_the_workloads_fails(
    copy: Path, old: str, new: str
) -> None:
    edit(copy / "free-path.yaml", old, new)
    assert any("workloads.yaml can use at once" in p for p in problems(copy))


def test_an_instance_quota_fails(copy: Path) -> None:
    # InstancesPerProject is 0 in us-central1 and governs Cloud Run Instances resources, not services or Jobs:
    # a preference of 4 raises it, and the API refuses that without a contact email.
    edit(
        copy / "free-path.yaml",
        "  cloud_run_regional_quotas:\n",
        "  cloud_run_regional_quotas:\n"
        "    run.googleapis.com/instances: {quota_id: InstancesPerProject, unit: instances, value: 4}\n",
    )
    assert any("unit 'instances', not one of" in p for p in problems(copy))


def test_cloud_run_quotas_are_what_the_workloads_use_at_once() -> None:
    # The agent at its cap, one task of each Job, one more agent instance for a rollout: 4 x (1 vCPU, 512 MiB).
    caps = yaml.safe_load((GCP / "free-path.yaml").read_text())["caps"]
    assert {
        q["unit"]: q["value"] for q in caps["cloud_run_regional_quotas"].values()
    } == {
        "milli_vcpu": 4000,
        "bytes": 4 * 512 * 2**20,
    }
