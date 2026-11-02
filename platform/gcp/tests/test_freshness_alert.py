"""The freshness alert's log-based metric (infra/monitoring.tf, #209) against dbt's real JSON log lines.

fixtures/dbt-source-freshness.jsonl is `dbt source freshness` output with DBT_LOG_FORMAT=json, captured on the
BigQuery emulator from the image's pins (dbt-core 1.12.6, dbt-bigquery 1.12.1; the GCP image's copy of dbt/):
synthetic_campaigns missing (runtime error), synthetic_customers loaded an hour ago (pass), synthetic_leads
30 hours ago (warn), synthetic_orders 40 hours ago (error), plus a LogStartLine and dbt's RunResultErrorNoMessage,
which also carries `data.status: error`. Cloud Run makes each JSON line a log entry's jsonPayload, under the
`cloud_run_job` resource labelled with the Job's name; the metric's filter is evaluated on such entries here,
with the subset of the Logging query language it uses (one comparison per line, implicitly ANDed).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

GCP = Path(__file__).resolve().parent.parent
REPO = GCP.parent.parent
MONITORING = (GCP / "infra" / "monitoring.tf").read_text()
LINES = (
    (Path(__file__).parent / "fixtures" / "dbt-source-freshness.jsonl")
    .read_text()
    .splitlines()
)
JOB = "dbt-source-freshness"


def metric_block() -> str:
    match = re.search(
        r'^resource "google_logging_metric" "stale_source" \{\n(.*?)^\}',
        MONITORING,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "infra/monitoring.tf declares the metric"
    return match.group(1)


def log_filter() -> list[tuple[str, list[str]]]:
    """The metric's filter as (field path, accepted values), one per line."""
    match = re.search(r"filter\s*=\s*<<-EOT\n(.*?)\n\s*EOT", metric_block(), re.DOTALL)
    assert match, "the filter is a heredoc, one comparison per line"
    out = []
    for line in match.group(1).strip().splitlines():
        m = re.fullmatch(r'\s*([A-Za-z_.]+)=(?:"([^"]*)"|\((.*)\))\s*', line)
        assert m, f"outside the subset this test evaluates: {line!r}"
        path, value, alternatives = m.groups()
        if value is None:
            assert re.fullmatch(r'"[^"]*"(?: OR "[^"]*")*', alternatives), line
            out.append((path, re.findall(r'"([^"]*)"', alternatives)))
        else:
            out.append((path, [value]))
    return out


def field(entry: dict, path: str) -> object:
    for part in path.split("."):
        if not isinstance(entry, dict) or part not in entry:
            return None
        entry = entry[part]
    return entry


def entry(line: str, job: str = JOB) -> dict:
    """A Cloud Run Job's log entry for one JSON line of its output."""
    return {
        "resource": {"type": "cloud_run_job", "labels": {"job_name": job}},
        "jsonPayload": json.loads(line),
    }


def matches(e: dict) -> bool:
    return all(field(e, path) in values for path, values in log_filter())


def extractors() -> dict[str, str]:
    block = re.search(r"label_extractors\s*=\s*\{(.*?)\}", metric_block(), re.DOTALL)
    assert block
    return dict(re.findall(r'(\w+)\s*=\s*"EXTRACT\(([^)]+)\)"', block.group(1)))


def test_the_metric_counts_stale_and_unchecked_tables_once_each() -> None:
    counted = [e for e in map(entry, LINES) if matches(e)]
    assert [
        (field(e, "jsonPayload.data.table_name"), field(e, "jsonPayload.data.status"))
        for e in counted
    ] == [("synthetic_campaigns", "runtime error"), ("synthetic_orders", "error")]


def test_the_fixture_holds_the_events_the_filter_must_skip() -> None:
    names = {json.loads(line)["info"]["name"] for line in LINES}
    assert names == {"LogFreshnessResult", "LogStartLine", "RunResultErrorNoMessage"}
    statuses = {
        json.loads(line)["data"].get("status")
        for line in LINES
        if json.loads(line)["info"]["name"] == "LogFreshnessResult"
    }
    assert statuses == {"pass", "warn", "error", "runtime error"}
    # Without info.name, dbt's summary line would count synthetic_orders a second time.
    summary = [line for line in LINES if "RunResultErrorNoMessage" in line]
    assert field(entry(summary[0]), "jsonPayload.data.status") == "error"
    assert not matches(entry(summary[0]))


def test_another_jobs_lines_are_not_counted() -> None:
    assert not any(matches(entry(line, job="dbt-build")) for line in LINES)


def test_each_label_is_extracted_from_the_counted_lines() -> None:
    labels = extractors()
    assert set(labels) == {"source", "table", "status"}
    declared = set(re.findall(r'key\s*=\s*"(\w+)"', metric_block()))
    assert declared == set(labels)
    for e in filter(matches, map(entry, LINES)):
        assert all(isinstance(field(e, path), str) for path in labels.values())


def test_the_metric_reads_the_freshness_job_of_workloads_yaml() -> None:
    job = yaml.safe_load((GCP / "workloads.yaml").read_text())["jobs"][JOB]
    assert job["env"]["DBT_LOG_FORMAT"] == "json"
    assert "dbt source freshness" in " ".join(job["command"])
    assert ("resource.labels.job_name", [JOB]) in log_filter()
    assert f'freshness_job   = "{JOB}"' in MONITORING


def test_the_series_stay_inside_the_free_metric_bytes() -> None:
    # One series per source, table and error status; the GCP image ships the root project's sources only.
    caps = yaml.safe_load((GCP / "free-path.yaml").read_text())["caps"]
    sources = yaml.safe_load((REPO / "dbt" / "models" / "sources.yml").read_text())
    checked = [
        t["name"]
        for s in sources["sources"]
        for t in s["tables"]
        if t.get("freshness", 1) is not None
        and (t.get("config") or {}).get("freshness", 1) is not None
    ]
    assert (
        len(checked) == 15
    )  # 16 landed tables; open_meteo_hourly_weather has no freshness
    statuses = dict(log_filter())["jsonPayload.data.status"]
    assert len(checked) * len(statuses) <= caps["log_metric_series"]


@pytest.mark.parametrize("unbounded", ["invocation_id", "ts", "node_info"])
def test_no_label_comes_from_a_per_run_field(unbounded: str) -> None:
    # A label per run (its id, its time) would make a series per run and grow past the free bytes.
    assert not any(unbounded in path for path in extractors().values())
