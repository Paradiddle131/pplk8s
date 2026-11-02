"""This month's usage of each free tier on the lab project, from sources minutes behind (#313).

`make gcp-usage-check`: one line per free-path.yaml `usage` entry: used, free tier, share, source.
Exit 0: every measured tier at or below `--share` percent of its free amount, or below its entry's own `share`.
Exit 1: one or more past it (a tier of 0, a SKU with no free tier, fails on any use).
Exit 3: a source could not be read: nothing is proven, so no live GCP work (as `make gcp-cost-check`'s 3).
Exit 1 wins over 3 when both apply: a tier known to be near its end is the more urgent news.
Entries with `free: null` are printed and never change the exit code.

Sources, all read-only: Cloud Monitoring's timeSeries (aggregated server-side, so each metric returns one series
per monitored resource type), checked first to exist (metricDescriptors.get, which bills nothing), so a misspelled
metric is an unreadable source rather than a zero; and three REST lists (Artifact Registry repositories, Cloud
Scheduler jobs, Secret Manager versions), where an API that is off counts as nothing used.
The month and the day start at 00:00 Pacific time, as Cloud Billing's months and Firestore's daily quota do.

Credentials: GOOGLE_OAUTH_ACCESS_TOKEN; else a cloud session's proxy-injected CLOUDSDK_AUTH_ACCESS_TOKEN; else
`gcloud auth print-access-token` for $GCP_ACCOUNT or the active account, as platform/gcp/tofu.sh borrows it.

Usage: python platform/gcp/usage_check.py [--share 50] [--project ID] [--region us-central1].
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import math
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

import yaml

FREE_PATH = Path(__file__).resolve().parent / "free-path.yaml"
BILLING_TZ = ZoneInfo("America/Los_Angeles")
GAUGE_LOOKBACK = dt.timedelta(days=7)
MONITORING = "https://monitoring.googleapis.com/v3"
WINDOWS = ("month", "day", "now")
READS = ("artifact_registry_bytes", "scheduler_jobs", "secret_versions")


class Unreadable(Exception):
    """A source answered with an error, or not at all: its usage is unknown."""


class ApiDisabled(Unreadable):
    """The product's API is off on the project, so nothing can have been used through it."""


class Gcp(Protocol):
    """The seam: one authenticated GET of a Google API, its JSON body back."""

    def get(self, url: str, params: dict[str, str] | None = None) -> dict: ...


@dataclasses.dataclass(frozen=True)
class Tier:
    name: str
    api: str
    free: float | None
    unit: str
    window: str
    source: str
    metrics: tuple[str, ...] = ()
    resource: str | None = None
    read: str | None = None
    note: str | None = None
    share: float | None = None  # the entry's own limit in percent, instead of --share
    warn: str | None = (
        None  # why this reading only warns: past its limit it is WARN, never OVER
    )


@dataclasses.dataclass(frozen=True)
class Line:
    tier: Tier
    status: str  # ok, OVER, WARN, UNKNOWN, info, not measured
    used: float | None = None
    detail: str = ""

    @property
    def share(self) -> float | None:
        return share(self.used, self.tier.free)


def tiers(spec: dict) -> list[Tier]:
    """free-path.yaml's `usage` entries as tiers; a malformed entry is a ValueError naming it."""
    out = []
    for entry in spec.get("usage") or []:
        metric = entry.get("metric")
        metrics = tuple(
            metric if isinstance(metric, list) else [metric] if metric else []
        )
        tier = Tier(
            name=entry["name"],
            api=entry["api"],
            free=entry["free"],
            unit=entry["unit"],
            window=entry["window"],
            source=entry["source"],
            metrics=metrics,
            resource=entry.get("resource"),
            read=entry.get("read"),
            note=entry.get("note"),
            share=entry.get("share"),
            warn=entry.get("warn"),
        )
        if tier.window not in WINDOWS:
            raise ValueError(
                f"{tier.name}: window {tier.window!r} is not one of {WINDOWS}"
            )
        if tier.read and (tier.read not in READS or tier.metrics):
            raise ValueError(
                f"{tier.name}: read must be one of {READS}, without a metric"
            )
        if tier.free is not None and not (tier.metrics or tier.read):
            raise ValueError(
                f"{tier.name}: a free tier needs a metric or a read to measure it"
            )
        if tier.free is None and not (tier.metrics or tier.note):
            raise ValueError(
                f"{tier.name}: an unmeasured entry needs a note saying why"
            )
        if tier.share is not None and not 0 < tier.share <= 100:
            raise ValueError(
                f"{tier.name}: its own share is a percent in (0, 100], not {tier.share}"
            )
        out.append(tier)
    return out


def window_start(window: str, now: dt.datetime) -> dt.datetime:
    """The window's start in UTC: the month's or the day's 00:00 Pacific time, or the gauge lookback."""
    if window == "now":
        return now - GAUGE_LOOKBACK
    local = now.astimezone(BILLING_TZ)
    day = local.date().replace(day=1) if window == "month" else local.date()
    start = dt.datetime.combine(day, dt.time(), tzinfo=BILLING_TZ)
    return start.astimezone(dt.UTC)


def share(used: float | None, free: float | None) -> float | None:
    """Used as a share of the free amount, in percent; any use of a zero tier is infinite."""
    if used is None or free is None:
        return None
    if free == 0:
        return math.inf if used > 0 else 0.0
    return 100.0 * used / free


def rfc3339(t: dt.datetime) -> str:
    return t.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def monitoring_total(
    gcp: Gcp,
    project: str,
    metric: str,
    resource: str | None,
    window: str,
    now: dt.datetime,
) -> float:
    """A metric over the window, summed across series: a DELTA's sum, or a GAUGE's newest point per series."""
    base = f"{MONITORING}/projects/{project}"
    kind = gcp.get(f"{base}/metricDescriptors/{metric}").get("metricKind")
    gauge = kind == "GAUGE"
    if gauge != (window == "now"):
        raise Unreadable(
            f"{metric} is a {kind} metric, which window {window} cannot read"
        )
    start = window_start(window, now)
    period = max(60, math.ceil((now - start).total_seconds()))
    query = f'metric.type = "{metric}"'
    if resource:
        query += f' AND resource.type = "{resource}"'
    params = {
        "filter": query,
        "interval.startTime": rfc3339(start),
        "interval.endTime": rfc3339(now),
        "aggregation.alignmentPeriod": f"{period}s",
        "aggregation.perSeriesAligner": "ALIGN_NEXT_OLDER" if gauge else "ALIGN_SUM",
        "aggregation.crossSeriesReducer": "REDUCE_SUM",
    }
    total = 0.0
    while True:
        body = gcp.get(f"{base}/timeSeries", params)
        for series in body.get("timeSeries", []):  # none: nothing used in the window
            for point in series.get("points", []):
                value = point["value"]
                total += float(value.get("int64Value", value.get("doubleValue", 0)))
        if not body.get("nextPageToken"):
            return total
        params = {**params, "pageToken": body["nextPageToken"]}


def listed(gcp: Gcp, url: str, key: str) -> list[dict]:
    """Every item of a paged REST list; an API that is off lists nothing."""
    items, params = [], {"pageSize": "100"}
    while True:
        try:
            body = gcp.get(url, params)
        except ApiDisabled:
            return []
        items += body.get(key, [])
        if not body.get("nextPageToken"):
            return items
        params = {**params, "pageToken": body["nextPageToken"]}


def rest_total(gcp: Gcp, project: str, region: str, read: str) -> float:
    if read == "artifact_registry_bytes":
        url = f"https://artifactregistry.googleapis.com/v1/projects/{project}/locations/{region}/repositories"
        return float(
            sum(int(r.get("sizeBytes", 0)) for r in listed(gcp, url, "repositories"))
        )
    if read == "scheduler_jobs":
        url = f"https://cloudscheduler.googleapis.com/v1/projects/{project}/locations/{region}/jobs"
        return float(len(listed(gcp, url, "jobs")))
    if read == "secret_versions":  # active versions: enabled or disabled, not destroyed
        url = f"https://secretmanager.googleapis.com/v1/projects/{project}/secrets"
        versions = 0
        for secret in listed(gcp, url, "secrets"):
            got = listed(
                gcp,
                f"https://secretmanager.googleapis.com/v1/{secret['name']}/versions",
                "versions",
            )
            versions += sum(1 for v in got if v.get("state") != "DESTROYED")
        return float(versions)
    raise Unreadable(f"no reader {read!r}")


def measure(gcp: Gcp, project: str, region: str, tier: Tier, now: dt.datetime) -> Line:
    if not (tier.metrics or tier.read):
        return Line(tier, "not measured", detail=tier.note or "")
    try:
        if tier.read:
            used = rest_total(gcp, project, region, tier.read)
            how = f"REST {tier.read}"
        else:
            used = sum(
                monitoring_total(gcp, project, m, tier.resource, tier.window, now)
                for m in tier.metrics
            )
            how = "Monitoring " + " + ".join(m.split("/", 1)[1] for m in tier.metrics)
            if tier.resource:
                how += f" on {tier.resource}"
    except Unreadable as e:
        return Line(tier, "UNKNOWN", detail=str(e))
    if tier.free is None:
        return Line(
            tier, "info", used, detail=f"{how}; {tier.note}" if tier.note else how
        )
    return Line(tier, "ok", used, detail=how)


def judge(lines: list[Line], threshold: float) -> tuple[list[Line], int]:
    """Mark each line past its limit (its entry's own share, else the threshold) OVER, or WARN when its entry
    says why it only warns; the exit code: 1 over, else 3 unknown, else 0 (a WARN is printed, not failed)."""
    out = [
        dataclasses.replace(
            line,
            status="WARN" if line.tier.warn else "OVER",
            detail=f"{line.detail}; warns only: {line.tier.warn}"
            if line.tier.warn
            else line.detail,
        )
        if line.status == "ok"
        and line.share is not None
        and line.share > limit(line.tier, threshold)
        else line
        for line in lines
    ]
    if any(line.status == "OVER" for line in out):
        return out, 1
    if any(line.status == "UNKNOWN" for line in out):
        return out, 3
    return out, 0


def limit(tier: Tier, threshold: float) -> float:
    return threshold if tier.share is None else tier.share


def amount(value: float | None, unit: str) -> str:
    if value is None:
        return "-"
    if unit == "bytes":
        for name, size in (
            ("TiB", 2**40),
            ("GiB", 2**30),
            ("MiB", 2**20),
            ("KiB", 2**10),
        ):
            if value >= size:
                return f"{value / size:.2f} {name}"
        return f"{value:.0f} B"
    return f"{value:,.0f} {unit}"


def render(line: Line) -> str:
    """One line: status, tier, used of free (and the window), share (and an entry's own limit), source."""
    t = line.tier
    pct = line.share
    pct_text = "-" if pct is None else "inf" if math.isinf(pct) else f"{pct:.1f}%"
    if t.share is not None:
        pct_text += f" (limit {t.share:g}%)"
    window = {"month": "this month", "day": "today", "now": "now"}[t.window]
    free = "-" if t.free is None else amount(t.free, t.unit)
    used = f"{amount(line.used, t.unit)} of {free} {window}"
    return f"  {line.status:<12} {t.name:<34} {used:<56} {pct_text:<19} {line.detail}"


def run(
    gcp: Gcp, spec: dict, project: str, region: str, threshold: float, now: dt.datetime
) -> tuple[list[str], int]:
    """The report's lines and the exit code: what main prints, without the network."""
    lines, code = judge(
        [measure(gcp, project, region, t, now) for t in tiers(spec)], threshold
    )
    month = window_start("month", now)
    out = [
        (
            f"gcp-usage-check: {project} from {rfc3339(month)} (the 1st, 00:00 Pacific) to {rfc3339(now)}; "
            f"fails past {threshold:g}% of a free tier (free tiers and their sources: platform/gcp/free-path.yaml)"
        )
    ]
    out += [render(line) for line in lines]
    over = [line.tier.name for line in lines if line.status == "OVER"]
    unknown = [line.tier.name for line in lines if line.status == "UNKNOWN"]
    if code == 1:
        out.append(f"gcp-usage-check: FAIL: past its limit: {', '.join(over)}")
    if unknown:
        out.append(
            f"gcp-usage-check: UNKNOWN: not readable, so not proven: {', '.join(unknown)}"
        )
    if code == 0:
        out.append(
            f"gcp-usage-check: ok: every measured free tier within its limit ({threshold:g}% unless its own)"
        )
    return out, code


class Http:
    """The real seam: urllib with a bearer token (the cloud proxy swaps in its own)."""

    def __init__(self, token: str, urlopen: Callable = urllib.request.urlopen):
        self.token = token
        self.urlopen = urlopen

    def get(self, url: str, params: dict[str, str] | None = None) -> dict:
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.token}"}
        )
        try:
            with self.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code == 403 and "SERVICE_DISABLED" in body:
                raise ApiDisabled(f"{url.split('?')[0]}: API not enabled") from e
            message = body
            try:
                message = json.loads(body)["error"]["message"]
            except (ValueError, KeyError, TypeError):
                pass
            raise Unreadable(
                f"{url.split('?')[0]}: HTTP {e.code}: {message.strip()[:200]}"
            ) from e
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise Unreadable(f"{url.split('?')[0]}: {e}") from e


def token() -> str:
    for name in ("GOOGLE_OAUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_ACCESS_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    account = os.environ.get("GCP_ACCOUNT")
    command = ["gcloud", "auth", "print-access-token"] + (
        [f"--account={account}"] if account else []
    )
    try:
        return subprocess.run(
            command, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        raise Unreadable(f"no credentials: {' '.join(command)} failed ({e})") from e


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--share", type=float, default=50.0, help="fail at this percent of a free tier"
    )
    parser.add_argument("--project", default=os.environ.get("GCP_PROJECT"))
    parser.add_argument(
        "--region", default=os.environ.get("GCP_REGION") or "us-central1"
    )
    args = parser.parse_args(argv)
    if not args.project:
        print(
            "gcp-usage-check: GCP_PROJECT is unset: the gcp- targets act on the lab project and need its id "
            "(platform/gcp/README.md)",
            file=sys.stderr,
        )
        return 2
    try:
        gcp = Http(token())
    except Unreadable as e:
        print(f"gcp-usage-check: UNKNOWN: {e}", file=sys.stderr)
        return 3
    spec = yaml.safe_load(FREE_PATH.read_text())
    lines, code = run(
        gcp, spec, args.project, args.region, args.share, dt.datetime.now(dt.UTC)
    )
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
