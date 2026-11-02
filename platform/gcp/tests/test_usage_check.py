"""usage_check.py offline, behind a fake of its one seam (an authenticated GET): the share math, the exit codes,
the month and day windows in Pacific time, and that the free tiers are free-path.yaml's (#313)."""

from __future__ import annotations

import datetime as dt
import io
import json
import math
import sys
import urllib.error
from pathlib import Path

import pytest
import yaml

GCP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GCP))

import usage_check as uc

SPEC = yaml.safe_load((GCP / "free-path.yaml").read_text())
NOW = dt.datetime(2026, 11, 2, 17, 0, tzinfo=dt.UTC)
UTC = dt.UTC


class FakeGcp:
    """Answers by URL: metric descriptors by metric, time series by the metric in the filter, REST lists by URL.
    A metric or URL absent from its table is an unreadable source."""

    def __init__(self, metrics=None, kinds=None, rest=None, fail=()):
        self.metrics = metrics or {}  # metric => total
        self.kinds = kinds or {}  # metric => metricKind, default DELTA
        self.rest = rest or {}  # url suffix => body
        self.fail = set(fail)  # metrics or url suffixes that fail
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        if "/metricDescriptors/" in url:
            metric = url.split("/metricDescriptors/", 1)[1]
            if metric in self.fail or metric not in self.metrics:
                raise uc.Unreadable(f"{metric}: HTTP 404")
            return {"type": metric, "metricKind": self.kinds.get(metric, "DELTA")}
        if url.endswith("/timeSeries"):
            metric = params["filter"].split('"')[1]
            total = self.metrics[metric]
            if total is None:
                return {}  # no series: nothing used
            return {"timeSeries": [{"points": [{"value": {"doubleValue": total}}]}]}
        for suffix, body in self.rest.items():
            if url.endswith(suffix):
                if suffix in self.fail:
                    raise uc.Unreadable(f"{url}: HTTP 500")
                if body == "disabled":
                    raise uc.ApiDisabled(f"{url}: API not enabled")
                return body
        raise uc.Unreadable(f"{url}: not faked")


def spec_of(*entries):
    return {"usage": list(entries)}


def entry(name="BigQuery queries", free=100, metric="m/a", window="month", **extra):
    return {
        "name": name,
        "api": "bigquery.googleapis.com",
        "free": free,
        "unit": "bytes",
        "window": window,
        "metric": metric,
        "source": "https://example.com/pricing",
        **extra,
    }


def run(gcp, spec, threshold=50.0, now=NOW):
    return uc.run(gcp, spec, "lab-test", "us-central1", threshold, now)


# The share math.


@pytest.mark.parametrize(
    ("used", "free", "expected"),
    [
        (0, 100, 0.0),
        (50, 100, 50.0),
        (1.5, 3, 50.0),
        (0, 0, 0.0),
        (None, 100, None),
        (5, None, None),
    ],
)
def test_share_is_used_over_free_in_percent(used, free, expected):
    assert uc.share(used, free) == expected


def test_any_use_of_a_tier_with_no_free_amount_is_an_infinite_share():
    assert math.isinf(uc.share(1, 0))


def test_exactly_the_threshold_passes_and_just_past_it_fails():
    _, at = run(FakeGcp(metrics={"m/a": 50}), spec_of(entry()))
    lines, past = run(FakeGcp(metrics={"m/a": 50.01}), spec_of(entry()))
    assert (at, past) == (0, 1)
    assert "OVER" in lines[1] and "50.0%" in lines[1]


def test_a_reading_that_only_warns_is_printed_past_its_limit_but_never_fails():
    spec = spec_of(entry(warn="a push's peak, not what bills"))
    lines, code = run(FakeGcp(metrics={"m/a": 900}), spec)
    assert code == 0
    assert "WARN" in lines[1] and "warns only: a push's peak" in lines[1]


def test_the_registry_gates_on_its_size_and_only_warns_on_the_gauge():
    registry = {
        e["name"]: e
        for e in SPEC["usage"]
        if e["api"] == "artifactregistry.googleapis.com"
    }
    assert "warn" not in registry["Artifact Registry storage"]
    assert registry["Artifact Registry storage (metric)"]["warn"]


def test_an_entrys_own_share_replaces_the_threshold():
    spec = spec_of(entry(name="Cloud Scheduler jobs", free=3, share=100))
    assert run(FakeGcp(metrics={"m/a": 3}), spec)[1] == 0
    assert run(FakeGcp(metrics={"m/a": 4}), spec)[1] == 1


def test_a_lower_threshold_fails_what_the_default_passes():
    gcp = FakeGcp(metrics={"m/a": 20})
    assert run(gcp, spec_of(entry()), threshold=50)[1] == 0
    assert run(gcp, spec_of(entry()), threshold=10)[1] == 1


# The exit codes.


def test_all_within_their_tiers_exits_0_and_says_ok():
    lines, code = run(
        FakeGcp(metrics={"m/a": 1, "m/b": None}),
        spec_of(entry(), entry(name="B", metric="m/b")),
    )
    assert code == 0
    assert lines[-1].startswith("gcp-usage-check: ok:")


def test_no_series_is_a_valid_zero():
    lines, code = run(FakeGcp(metrics={"m/a": None}), spec_of(entry()))
    assert code == 0
    assert " 0 B of " in lines[1]


def test_a_tier_past_its_share_exits_1_and_names_it():
    lines, code = run(
        FakeGcp(metrics={"m/a": 1, "m/b": 90}),
        spec_of(entry(), entry(name="Cloud Run", metric="m/b")),
    )
    assert code == 1
    assert lines[-1] == "gcp-usage-check: FAIL: past its limit: Cloud Run"


def test_any_use_of_a_zero_tier_exits_1():
    _, code = run(
        FakeGcp(metrics={"m/a": 1}),
        spec_of(entry(name="BigQuery streaming inserts", free=0)),
    )
    assert code == 1


def test_an_unreadable_metric_exits_3_never_ok():
    lines, code = run(
        FakeGcp(metrics={"m/a": 1}, fail={"m/b"}),
        spec_of(entry(), entry(name="B", metric="m/b")),
    )
    assert code == 3
    assert "UNKNOWN" in lines[2]
    assert not any(line.startswith("gcp-usage-check: ok") for line in lines)


def test_a_metric_that_does_not_exist_is_unreadable_not_zero():
    _, code = run(FakeGcp(metrics={}), spec_of(entry(metric="m/misspelt")))
    assert code == 3


def test_a_failing_rest_read_exits_3():
    spec = spec_of(
        entry(
            name="Cloud Scheduler jobs",
            free=3,
            metric=None,
            read="scheduler_jobs",
            window="now",
        )
    )
    _, code = run(FakeGcp(rest={"/jobs": {}}, fail={"/jobs"}), spec)
    assert code == 3


def test_over_wins_over_unknown():
    lines, code = run(
        FakeGcp(metrics={"m/a": 99}, fail={"m/b"}),
        spec_of(entry(), entry(name="B", metric="m/b")),
    )
    assert code == 1
    assert lines[-1].startswith("gcp-usage-check: UNKNOWN:")


def test_unmeasured_and_information_lines_never_change_the_exit_code():
    spec = spec_of(
        entry(name="Eventarc events", free=None, metric=None, note="no tier"),
        entry(
            name="Data agents tokens",
            free=None,
            metric="m/t",
            note="free trial until 2026-12-31",
        ),
    )
    lines, code = run(FakeGcp(metrics={"m/t": 10**9}), spec)
    assert code == 0
    assert "not measured" in lines[1] and "no tier" in lines[1]
    assert "info" in lines[2] and "free trial until 2026-12-31" in lines[2]


def test_a_gauge_read_as_a_monthly_sum_is_refused():
    gcp = FakeGcp(metrics={"m/a": 1}, kinds={"m/a": "GAUGE"})
    assert run(gcp, spec_of(entry(window="month")))[1] == 3
    assert run(gcp, spec_of(entry(window="now")))[1] == 0


# The windows.


@pytest.mark.parametrize(
    ("now", "start"),
    [
        # Daylight time ends on 2026-11-01 at 02:00 PDT: that month began at 00:00 PDT, 07:00Z.
        (NOW, dt.datetime(2026, 11, 1, 7, tzinfo=UTC)),
        # 2026-11-01T06:59Z is still 31 October in Pacific time.
        (
            dt.datetime(2026, 11, 1, 6, 59, tzinfo=UTC),
            dt.datetime(2026, 10, 1, 7, tzinfo=UTC),
        ),
        # Standard time: 00:00 PST is 08:00Z.
        (
            dt.datetime(2026, 12, 15, 12, tzinfo=UTC),
            dt.datetime(2026, 12, 1, 8, tzinfo=UTC),
        ),
        (
            dt.datetime(2027, 1, 1, 7, 59, tzinfo=UTC),
            dt.datetime(2026, 12, 1, 8, tzinfo=UTC),
        ),
        (
            dt.datetime(2027, 1, 1, 8, 0, tzinfo=UTC),
            dt.datetime(2027, 1, 1, 8, tzinfo=UTC),
        ),
    ],
)
def test_the_month_starts_at_midnight_pacific_on_the_1st(now, start):
    assert uc.window_start("month", now) == start


def test_the_day_starts_at_midnight_pacific_and_now_looks_back_a_week():
    assert uc.window_start("day", NOW) == dt.datetime(2026, 11, 2, 8, tzinfo=UTC)
    assert uc.window_start("now", NOW) == NOW - dt.timedelta(days=7)


def test_the_monthly_query_sums_since_the_month_start_in_one_window():
    gcp = FakeGcp(metrics={"m/a": 1})
    run(gcp, spec_of(entry(resource="cloud_run_job")))
    params = next(p for url, p in gcp.calls if url.endswith("/timeSeries"))
    assert params["interval.startTime"] == "2026-11-01T07:00:00Z"
    assert params["interval.endTime"] == "2026-11-02T17:00:00Z"
    assert params["aggregation.alignmentPeriod"] == f"{34 * 3600}s"
    assert params["aggregation.perSeriesAligner"] == "ALIGN_SUM"
    assert params["aggregation.crossSeriesReducer"] == "REDUCE_SUM"
    assert params["filter"] == 'metric.type = "m/a" AND resource.type = "cloud_run_job"'


def test_a_gauge_takes_each_series_newest_point():
    gcp = FakeGcp(metrics={"m/a": 1}, kinds={"m/a": "GAUGE"})
    run(gcp, spec_of(entry(window="now")))
    params = next(p for url, p in gcp.calls if url.endswith("/timeSeries"))
    assert params["aggregation.perSeriesAligner"] == "ALIGN_NEXT_OLDER"


def test_a_metric_list_is_summed():
    lines, code = run(
        FakeGcp(metrics={"m/a": 30, "m/b": 30}), spec_of(entry(metric=["m/a", "m/b"]))
    )
    assert code == 1
    assert "60.0%" in lines[1]


# The REST reads.


def test_rest_reads_count_registry_bytes_scheduler_jobs_and_active_secret_versions():
    project = "projects/lab-test"
    gcp = FakeGcp(
        rest={
            "/repositories": {
                "repositories": [{"sizeBytes": "300"}, {"sizeBytes": "200"}]
            },
            "/locations/us-central1/jobs": {"jobs": [{}, {}]},
            f"{project}/secrets": {"secrets": [{"name": f"{project}/secrets/key"}]},
            "/secrets/key/versions": {
                "versions": [
                    {"state": "ENABLED"},
                    {"state": "DISABLED"},
                    {"state": "DESTROYED"},
                ]
            },
        }
    )
    assert (
        uc.rest_total(gcp, "lab-test", "us-central1", "artifact_registry_bytes") == 500
    )
    assert uc.rest_total(gcp, "lab-test", "us-central1", "scheduler_jobs") == 2
    assert uc.rest_total(gcp, "lab-test", "us-central1", "secret_versions") == 2


def test_an_api_that_is_off_has_used_nothing():
    gcp = FakeGcp(rest={"/locations/us-central1/jobs": "disabled"})
    assert uc.rest_total(gcp, "lab-test", "us-central1", "scheduler_jobs") == 0


def test_a_rest_list_follows_its_pages():
    class Paged(FakeGcp):
        def get(self, url, params=None):
            self.calls.append((url, dict(params or {})))
            if "pageToken" in (params or {}):
                return {"jobs": [{}]}
            return {"jobs": [{}, {}], "nextPageToken": "t"}

    assert uc.rest_total(Paged(), "lab-test", "us-central1", "scheduler_jobs") == 3


# The real seam's error handling, on a fake urlopen.


def http_error(code, body):
    return urllib.error.HTTPError(
        "https://x", code, "err", {}, io.BytesIO(json.dumps(body).encode())
    )


def test_http_maps_service_disabled_to_api_disabled_and_other_errors_to_unreadable():
    def disabled(request, timeout):
        raise http_error(
            403,
            {"error": {"message": "x", "details": [{"reason": "SERVICE_DISABLED"}]}},
        )

    def denied(request, timeout):
        raise http_error(
            403, {"error": {"message": "Permission monitoring.timeSeries.list denied"}}
        )

    with pytest.raises(uc.ApiDisabled):
        uc.Http("t", urlopen=disabled).get("https://cloudscheduler.googleapis.com/v1/x")
    with pytest.raises(
        uc.Unreadable, match="HTTP 403: Permission monitoring.timeSeries.list denied"
    ):
        uc.Http("t", urlopen=denied).get("https://monitoring.googleapis.com/v3/x")


# The free tiers come from free-path.yaml.


def test_the_free_tiers_are_free_path_yamls():
    by_name = {t.name: t for t in uc.tiers(SPEC)}
    assert by_name["BigQuery queries"].free == 2**40
    assert by_name["BigQuery storage"].free == 10 * 2**30
    assert by_name["Cloud Run services vCPU"].free == 180_000
    assert by_name["Cloud Run Jobs vCPU"].free == 240_000
    assert by_name["Artifact Registry storage"].free == 2**29
    assert by_name["Firestore reads"].window == "day"


def test_a_changed_free_tier_in_the_spec_changes_the_verdict():
    spec = {
        "usage": [dict(e) for e in SPEC["usage"] if e["name"] == "BigQuery queries"]
    }
    gcp = FakeGcp(
        metrics={
            "bigquery.googleapis.com/query/statement_scanned_bytes_billed": 100 * 2**30
        }
    )
    assert run(gcp, spec)[1] == 0
    spec["usage"][0]["free"] = 150 * 2**30
    assert run(gcp, spec)[1] == 1


def test_every_usage_entry_is_well_formed_and_on_the_free_path():
    allowed = set(SPEC["apis"]) | set(SPEC.get("implicit") or {})
    tiers = uc.tiers(SPEC)  # raises on a malformed entry
    assert len({t.name for t in tiers}) == len(tiers)
    for t in tiers:
        assert t.api in allowed, t.name
        assert t.source.startswith("https://"), t.name
        assert all(
            m.startswith(t.api.replace(".googleapis.com", ".googleapis.com/"))
            for m in t.metrics
        ), t.name


def test_every_enabled_api_with_usage_charges_has_an_entry():
    # The control-plane APIs bill nothing; every other enabled API must say how its usage is counted.
    control = {
        "serviceusage.googleapis.com",
        "cloudresourcemanager.googleapis.com",
        "iam.googleapis.com",
        "cloudquotas.googleapis.com",
        "billingbudgets.googleapis.com",
        "cloudbilling.googleapis.com",
        "bigquerystorage.googleapis.com",
        "bigquerydatatransfer.googleapis.com",
        "workflowexecutions.googleapis.com",
    }
    enabled = {name for name, api in SPEC["apis"].items() if api.get("enable")}
    covered = {t.api for t in uc.tiers(SPEC)}
    assert enabled - control - covered == set()


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ({"window": "week"}, "window"),
        ({"metric": None}, "needs a metric or a read"),
        ({"read": "bogus", "metric": None}, "read must be"),
        ({"free": None, "metric": None}, "needs a note"),
        ({"share": 150}, "its own share"),
    ],
)
def test_a_malformed_entry_is_refused(bad, message):
    with pytest.raises(ValueError, match=message):
        uc.tiers(spec_of(entry(**bad)))
