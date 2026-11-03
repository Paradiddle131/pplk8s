"""Lightdash's numbers beside MetricFlow's on data, for every metric Lightdash translated (#363, Q9).

What it measures: for each MetricFlow metric that open-source Lightdash translated into one of its
explores (36 of 56 in #334), two fixed queries asked both ways on the same database:
  - `total`: the metric with no dimension and no filter, over every row the fixture holds;
  - `by_day`: the metric by its own time dimension at day grain (MetricFlow's `metric_time__day`,
    Lightdash's `<model>_<agg_time_dimension>_day`), every day either side returns.
Lightdash answers through its free query API (`POST /api/v2/projects/<p>/query/metric-query`, then
`GET .../query/<uuid>` until ready); MetricFlow through the semantic agent's own tool path
(`semantic_agent.metrics.run`, MetricFlow's engine on `dbt/`, the `agent_metrics` role).
A value matches when |lightdash - metricflow| <= 1e-6 or the relative gap is <= 1e-9; `by_day` matches
when every day either side returns matches, except a day one side gives as 0 and the other leaves out
or returns as null (no qualifying row: counted as zero-filled, listed apart). Prints one line per metric and a summary,
and writes every value to `--out` (JSON).

Env: dbt's connection (`DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=dbt_dev DBT_USER=agent_metrics
DBT_PASSWORD=agent_metrics`), `dbt/` parsed for that database with its catalog written (`dbt parse`,
`dbt/scripts/build_catalog.py`); a Lightdash server from probes/334_lightdash_server.sh (`--keep`,
`DBT_DBNAME=dbt_dev LIGHTDASH_WAREHOUSE_CATALOG=1`), whose out-dir holds token.txt and project.txt;
`LIGHTDASH_URL` (default http://localhost:8080).
Run from services/semantic-agent (hold the warehouse lock shared):
  uv run python ../../docs/research/semantic-bet/probes/363_lightdash_numbers.py [ld-out-dir] [--out file]
Offline: the Compose warehouse and the local Lightdash only; no model is called.
Exit 0: every translated metric compared (matching or not); 1: setup failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from semantic_agent import metrics

ABS_TOL = 1e-6
REL_TOL = 1e-9


class Lightdash:
    def __init__(self, url: str, token: str, project: str) -> None:
        self.url, self.token, self.project = url.rstrip("/"), token, project

    def call(self, path: str, body: dict[str, Any] | None = None) -> Any:
        request = urllib.request.Request(
            f"{self.url}/api{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"ApiKey {self.token}",
                "content-type": "application/json",
            },
            method="POST" if body is not None else "GET",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)["results"]

    def explores(self) -> list[dict[str, Any]]:
        return [
            self.call(f"/v1/projects/{self.project}/explores/{e['name']}")
            for e in self.call(f"/v1/projects/{self.project}/explores")
            if not e.get("errors")
        ]

    def query(
        self, explore: str, dimensions: list[str], metric_ids: list[str]
    ) -> list[dict]:
        """Rows of a metric query through the async v2 API, each field's raw value."""
        started = self.call(
            f"/v2/projects/{self.project}/query/metric-query",
            {
                "query": {
                    "exploreName": explore,
                    "dimensions": dimensions,
                    "metrics": metric_ids,
                    "filters": {},
                    "sorts": [],
                    "limit": 5000,
                    "tableCalculations": [],
                },
                "context": "api",
            },
        )
        rows: list[dict] = []
        page = 1
        for _ in range(120):
            result = self.call(
                f"/v2/projects/{self.project}/query/{started['queryUuid']}?page={page}&pageSize=500"
            )
            if result["status"] == "error":
                raise RuntimeError(result.get("error"))
            if result["status"] != "ready":
                time.sleep(0.5)
                continue
            rows += [
                {k: v["value"]["raw"] for k, v in r.items()} for r in result["rows"]
            ]
            if page >= result["totalPageCount"]:
                return rows
            page += 1
        raise TimeoutError(f"{explore}: query not ready")


def number(value: Any) -> float | None:
    return None if value is None else float(value)


def same(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) <= ABS_TOL or abs(a - b) <= REL_TOL * max(abs(a), abs(b))


def translated(
    explores: list[dict[str, Any]], names: set[str]
) -> dict[str, dict[str, Any]]:
    """Each MetricFlow metric Lightdash holds: its explore, table, field id and day dimensions."""
    found: dict[str, dict[str, Any]] = {}
    for explore in explores:
        table = explore["tables"][explore["baseTable"]]
        for name in table["metrics"]:
            if name in names and name not in found:
                days = [
                    f"{explore['baseTable']}_{d}"
                    for d, spec in table["dimensions"].items()
                    if spec.get("timeInterval") == "DAY"
                ]
                found[name] = {
                    "explore": explore["name"],
                    "field": f"{explore['baseTable']}_{name}",
                    "day_dimensions": days,
                }
    return found


def agg_time(manifest: dict[str, Any], metric: dict[str, Any]) -> str | None:
    """The metric's time dimension: a simple metric's own (dbt 1.12 metrics carry their aggregation),
    else its semantic model's default; a ratio's is its numerator's."""
    params = metric["type_params"]
    if params.get("numerator"):
        inputs = {m["name"]: m for m in manifest["metrics"].values()}
        return agg_time(manifest, inputs[params["numerator"]["name"]])
    aggregation = params.get("metric_aggregation_params") or {}
    if aggregation.get("agg_time_dimension"):
        return aggregation["agg_time_dimension"]
    for model in manifest["semantic_models"].values():
        if model["name"] == aggregation.get("semantic_model"):
            return model["defaults"].get("agg_time_dimension")
    return None


def metricflow(
    name: str, catalog: metrics.Catalog, by_day: bool
) -> list[dict[str, Any]]:
    query = metrics.MetricQuery(
        metrics=[name], group_by=["metric_time__day"] if by_day else []
    )
    result = metrics.run(query, catalog)
    if result["row_count"] >= metrics.MAX_ROWS:
        raise RuntimeError(f"{name}: MetricFlow's {metrics.MAX_ROWS}-row cap reached")
    return result["rows"]


def compare(
    name: str, spec: dict[str, Any], ld: Lightdash, catalog: metrics.Catalog
) -> dict:
    out: dict[str, Any] = {"metric": name, **spec}
    mf_total = number(metricflow(name, catalog, False)[0][name])
    ld_rows = ld.query(spec["explore"], [], [spec["field"]])
    ld_total = number(ld_rows[0][spec["field"]]) if ld_rows else None
    out["total"] = {
        "metricflow": mf_total,
        "lightdash": ld_total,
        "match": same(ld_total, mf_total),
    }

    day = f"{spec['explore']}_{spec['agg_time']}_day"
    if day not in spec["day_dimensions"]:
        out["by_day"] = {"match": None, "why": f"no day dimension {day} in the explore"}
        return out
    mf = {
        r["metric_time__day"][:10]: number(r[name])
        for r in metricflow(name, catalog, True)
    }
    ldd = {
        str(r[day])[:10]: number(r[spec["field"]])
        for r in ld.query(spec["explore"], [day], [spec["field"]])
    }
    # A day one side returns as null and the other leaves out holds no number either way.
    mf = {k: v for k, v in mf.items() if v is not None}
    ldd = {k: v for k, v in ldd.items() if v is not None}
    differ = sorted(k for k in set(mf) | set(ldd) if not same(ldd.get(k), mf.get(k)))
    # A day with no qualifying row: one side says 0, the other returns no number. Kept apart from a
    # different number, since every figure both sides give still agrees.
    zero = [k for k in differ if {mf.get(k), ldd.get(k)} == {None, 0.0}]
    out["by_day"] = {
        "days_metricflow": len(mf),
        "days_lightdash": len(ldd),
        "range": [min(mf | ldd), max(mf | ldd)] if mf or ldd else None,
        "zero_filled": {
            k: "lightdash" if ldd.get(k) == 0.0 else "metricflow" for k in zero
        },
        "days_differ": [
            {"day": k, "metricflow": mf.get(k), "lightdash": ldd.get(k)}
            for k in differ
            if k not in zero
        ],
    }
    out["by_day"]["match"] = not out["by_day"]["days_differ"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "ld_dir",
        nargs="?",
        type=Path,
        default=Path(os.environ.get("TMPDIR", "/tmp")) / "semantic-bet-334-lightdash",
    )
    parser.add_argument("--out", type=Path, help="write every value here (JSON)")
    args = parser.parse_args()
    ld = Lightdash(
        os.environ.get("LIGHTDASH_URL", "http://localhost:8080"),
        (args.ld_dir / "token.txt").read_text().strip(),
        (args.ld_dir / "project.txt").read_text().strip(),
    )
    manifest = json.loads(
        (metrics.project_dir() / "target" / "manifest.json").read_text()
    )
    by_name = {m["name"]: m for m in manifest["metrics"].values()}
    catalog = metrics.Catalog.load()
    found = translated(ld.explores(), set(by_name))
    print(f"Lightdash holds {len(found)} of {len(by_name)} MetricFlow metrics")
    results = []
    for name in sorted(found):
        spec = {
            **found[name],
            "type": by_name[name]["type"],
            "agg_time": agg_time(manifest, by_name[name]),
        }
        try:
            r = compare(name, spec, ld, catalog)  # one metric's failure is its row
        except (
            RuntimeError,
            OSError,
            ValueError,
            KeyError,
            IndexError,
            TimeoutError,
            metrics.QueryError,
        ) as e:
            r = {"metric": name, **spec, "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        if "error" in r:
            print(f"{name} ({spec['type']}): not comparable: {r['error']}")
            continue
        t, d = r["total"], r["by_day"]
        days = (
            f"{d['days_metricflow']} / {d['days_lightdash']} days"
            + (f", {len(d['zero_filled'])} zero-filled" if d["zero_filled"] else "")
            if d["match"] is not None
            else d["why"]
        )
        print(
            f"{name} ({spec['type']}, {spec['explore']}): total mf {t['metricflow']} ld {t['lightdash']} "
            f"{'=' if t['match'] else '≠'}; by day {days} {'=' if d['match'] else '≠'}"
        )
    matched = [
        r
        for r in results
        if "error" not in r and r["total"]["match"] and r["by_day"]["match"]
    ]
    broken = [r for r in results if "error" in r or r["by_day"]["match"] is None]
    print(
        f"summary: {len(matched)} matched, {len(results) - len(matched) - len(broken)} mismatched, "
        f"{len(broken)} not comparable, of {len(results)}"
    )
    if args.out:
        args.out.write_text(json.dumps(results, indent=1, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
