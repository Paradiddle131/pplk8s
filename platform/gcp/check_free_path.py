"""Fail when platform/gcp/ reaches beyond the free path (semantic/PLAN.md SL-13), offline.

Checks, against free-path.yaml:
- every API listed has an https source and is not on its `paid` list;
- an API past its `until` date is not enabled;
- every resource type the OpenTofu root declares is listed, and its API is enabled;
- every `*.googleapis.com` host the root names (resources, workflow sources) is an enabled API;
- every API GCP enables by itself (`implicit`) has an https source and is not paid;
- the daily query cap, every day of a 31-day month, stays inside BigQuery's free 1 TiB of queries;
- Cloud Run (#209): no public invoker, no service with a minimum instance, a maximum above
  `caps.cloud_run_max_instances` or CPU outside requests, one task and one attempt per Job run;
  workloads.yaml's scheduled Jobs, each run for its whole timeout, inside the Jobs' free vCPU- and
  GiB-seconds, and no more Scheduler jobs than `caps.cloud_scheduler_jobs`, itself at most the free three.

Usage: python platform/gcp/check_free_path.py [gcp dir]; run by `make gcp-validate`.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import yaml

FREE_QUERY_MIB_PER_MONTH = (
    1024 * 1024
)  # 1 TiB: https://cloud.google.com/bigquery/pricing#free-tier
# Cloud Run (https://cloud.google.com/run/pricing), per billing account a month: Jobs bill each instance's
# whole life, at least a minute; Cloud Scheduler (https://cloud.google.com/scheduler/pricing): 3 jobs.
FREE_JOB_VCPU_SECONDS = 240_000
FREE_JOB_GIB_SECONDS = 450_000
JOB_MINIMUM_S = 60
FREE_SCHEDULER_JOBS = 3
RESOURCE = re.compile(r'^\s*resource\s+"([a-z0-9_]+)"', re.MULTILINE)
PUBLIC = re.compile(r"\ball(?:Authenticated)?Users\b")
COMMENT = re.compile(r"^\s*(?:#|//).*$", re.MULTILINE)
SETTING = re.compile(
    r"^\s*([a-z_]+)\s*=\s*([0-9]+|true|false)\s*(?:#.*)?$", re.MULTILINE
)
HOST = re.compile(r"\b([a-z0-9-]+\.googleapis\.com)\b")


def problems(gcp: Path, today: dt.date | None = None) -> list[str]:
    today = today or dt.datetime.now(dt.UTC).date()
    spec = yaml.safe_load((gcp / "free-path.yaml").read_text())
    apis: dict[str, dict] = spec.get("apis") or {}
    resources: dict[str, str] = spec.get("resources") or {}
    paid = set(spec.get("paid") or [])
    out: list[str] = []

    for name, api in apis.items():
        if name in paid:
            out.append(f"{name}: on the paid list, so it cannot be on the free path")
        if not str(api.get("source", "")).startswith("https://"):
            out.append(f"{name}: no https source for its free tier")
        until = api.get("until")
        if until and api.get("enable") and today > dt.date.fromisoformat(str(until)):
            out.append(f"{name}: enabled past its free window ({until})")
    enabled = {name for name, api in apis.items() if api.get("enable")}

    for name, api in (spec.get("implicit") or {}).items():
        if name in paid:
            out.append(f"{name}: on the paid list, so it cannot be implicit")
        if name in apis:
            out.append(f"{name}: listed both as a free-path API and as implicit")
        if not str((api or {}).get("source", "")).startswith("https://"):
            out.append(f"{name}: an implicit API without an https source")

    caps = spec.get("caps") or {}
    daily = caps.get("bigquery_query_mib_per_day")
    if not isinstance(daily, int) or daily <= 0:
        out.append(
            "caps.bigquery_query_mib_per_day: missing; the query quota is the hard stop"
        )
    elif daily * 31 > FREE_QUERY_MIB_PER_MONTH:
        out.append(
            f"caps.bigquery_query_mib_per_day: {daily} MiB a day can bill past the free 1 TiB in a month"
        )
    per_job = caps.get("bigquery_maximum_bytes_billed")
    if not isinstance(per_job, int) or per_job <= 0:
        out.append("caps.bigquery_maximum_bytes_billed: missing")
    elif isinstance(daily, int) and per_job > daily * 1024 * 1024:
        out.append(
            "caps.bigquery_maximum_bytes_billed: one job may bill more than a day's quota"
        )

    out += workload_problems(gcp, caps)
    infra = gcp / "infra"
    schedulers = 0
    for path in sorted([*infra.glob("*.tf"), *infra.glob("*.yaml")]):
        text = path.read_text()
        if path.suffix == ".tf":
            out += run_problems(path.name, text, caps)
            schedulers += RESOURCE.findall(text).count("google_cloud_scheduler_job")
        for kind in RESOURCE.findall(text):
            api = resources.get(kind)
            if api is None:
                out.append(f"{path.name}: resource type {kind} is not on the free path")
            elif api not in enabled:
                out.append(f"{path.name}: {kind} needs {api}, which is not enabled")
        for host in HOST.findall(text):
            if host not in enabled:
                out.append(
                    f"{path.name}: names {host}, which is not an enabled free-path API"
                )
    if schedulers > 1:
        out.append(
            "infra: one google_cloud_scheduler_job resource, over workloads.yaml's schedules, so the cap counts them all"
        )
    return out


def run_problems(name: str, text: str, caps: dict) -> list[str]:
    """Literal settings in one .tf file that would bill Cloud Run outside the free path."""
    code = COMMENT.sub("", text)
    out = []
    if PUBLIC.search(code):
        out.append(
            f"{name}: a public member (allUsers, allAuthenticatedUsers); Cloud Run callers are IAM's"
        )
    cap = caps.get("cloud_run_max_instances")
    for key, value in SETTING.findall(code):
        if key == "invoker_iam_disabled" and value == "true":
            out.append(f"{name}: invoker_iam_disabled = true makes a service public")
        elif key == "cpu_idle" and value == "false":
            out.append(
                f"{name}: cpu_idle = false bills CPU outside requests (instance-based billing)"
            )
        elif key == "min_instance_count" and int(value) > 0:
            out.append(f"{name}: min_instance_count = {value} bills idle instances")
        elif key == "max_instance_count" and isinstance(cap, int) and int(value) > cap:
            out.append(
                f"{name}: max_instance_count = {value}, above caps.cloud_run_max_instances ({cap})"
            )
        elif key in ("task_count", "parallelism") and int(value) != 1:
            out.append(
                f"{name}: {key} = {value}; the Jobs' free-tier budget counts one instance per run"
            )
        elif key == "max_retries" and int(value) != 0:
            out.append(
                f"{name}: max_retries = {value}; the Jobs' free-tier budget counts one attempt per run"
            )
    if '"google_cloud_run_v2_service"' in code:
        for key in ("max_instance_count", "cpu_idle"):
            if not re.search(rf"^\s*{key}\s*=", code, re.MULTILINE):
                out.append(
                    f"{name}: a Cloud Run service without {key}: its default is not the free path's"
                )
    return out


def cron_values(field: str, low: int, high: int) -> set[int]:
    """The values one cron field takes: `*`, numbers, ranges, lists and steps."""
    values: set[int] = set()
    for part in field.split(","):
        base, _, step = part.partition("/")
        if base == "*":
            start, end = low, high
        elif "-" in base:
            start, end = (int(v) for v in base.split("-"))
        else:
            start = int(base)
            end = high if step else start
        values |= set(range(start, end + 1, int(step or 1)))
    return values


def runs_per_month(schedule: str) -> int:
    """At most how many times a five-field cron schedule fires in a month (31 days, five of each weekday)."""
    minute, hour, dom, _month, dow = schedule.split()
    days = 31
    if dom != "*" or dow != "*":
        by_date = len(cron_values(dom, 1, 31)) if dom != "*" else 0
        by_weekday = (
            5 * len({d % 7 for d in cron_values(dow, 0, 7)}) if dow != "*" else 0
        )
        days = min(31, by_date + by_weekday)
    return len(cron_values(minute, 0, 59)) * len(cron_values(hour, 0, 23)) * days


def gib(memory: str) -> float:
    """A Cloud Run memory limit (`512Mi`, `1Gi`) in GiB."""
    number, unit = re.fullmatch(r"(\d+)(Mi|Gi)", str(memory)).groups()
    return int(number) / (1024 if unit == "Mi" else 1)


def workload_problems(gcp: Path, caps: dict) -> list[str]:
    """workloads.yaml against the caps and Cloud Run's and Cloud Scheduler's free tiers."""
    path = gcp / "workloads.yaml"
    if not path.exists():
        return []
    spec = yaml.safe_load(path.read_text()) or {}
    out = []
    instances = caps.get("cloud_run_max_instances")
    if not isinstance(instances, int) or instances <= 0:
        out.append(
            "caps.cloud_run_max_instances: missing; Cloud Run's default is 100 instances"
        )
    schedulers = caps.get("cloud_scheduler_jobs")
    if not isinstance(schedulers, int) or not 0 < schedulers <= FREE_SCHEDULER_JOBS:
        out.append(
            f"caps.cloud_scheduler_jobs: {schedulers}; the billing account has {FREE_SCHEDULER_JOBS} free jobs"
        )
    vcpu = memory = 0.0
    scheduled = 0
    for name, job in (spec.get("jobs") or {}).items():
        if not job.get("schedule"):
            continue
        scheduled += 1
        try:
            runs = runs_per_month(job["schedule"])
            seconds = runs * max(int(job["timeout_s"]), JOB_MINIMUM_S)
            vcpu += seconds * float(job["cpu"])
            memory += seconds * gib(job["memory"])
        except (KeyError, ValueError, AttributeError) as e:
            out.append(f"workloads.yaml: {name}: cannot size its worst case ({e!r})")
    if vcpu > FREE_JOB_VCPU_SECONDS:
        out.append(
            f"workloads.yaml: the scheduled Jobs may use {vcpu:,.0f} vCPU-seconds a month, above the free {FREE_JOB_VCPU_SECONDS:,}"
        )
    if memory > FREE_JOB_GIB_SECONDS:
        out.append(
            f"workloads.yaml: the scheduled Jobs may use {memory:,.0f} GiB-seconds a month, above the free {FREE_JOB_GIB_SECONDS:,}"
        )
    if isinstance(schedulers, int) and scheduled > schedulers:
        out.append(
            f"workloads.yaml: {scheduled} scheduled Jobs, above caps.cloud_scheduler_jobs ({schedulers})"
        )
    return out


def main() -> int:
    gcp = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    found = problems(gcp)
    for p in found:
        print(f"free path: {p}", file=sys.stderr)
    if not found:
        print("free path: every API and resource type is on the allowlist")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
