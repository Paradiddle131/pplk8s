"""Fail when the target-architecture brief's metric table strays from the semantic layer (docs/target-architecture.md).

The brief's "Where each calculated field lives" table holds one row per metric, the rows semantic.metrics holds:
its name, label, type and semantic models, and the YAML file that defines it. This check reads the manifests
`dbt parse` writes, with no warehouse, and fails on a metric missing from the table, a row naming no metric,
or a row whose label, type, semantic models or file differ from the project's.

Usage: python scripts/check_brief.py [target_dir] [brief]  (after `dbt parse`; brief defaults to
../docs/target-architecture.md beside the dbt project)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HEADING = "## Where each calculated field lives"
COLUMNS = ("metric", "label", "type", "semantic models", "defined in")
CODE = re.compile(r"`([^`]+)`")


def semantic_models_of(name: str, metrics: dict[str, dict]) -> set[str]:
    """The semantic models a metric reads, through the metrics it is built from (as semantic_metrics.sql)."""
    params = metrics[name]["type_params"]
    aggregation = params.get("metric_aggregation_params") or {}
    if aggregation.get("semantic_model"):
        return {aggregation["semantic_model"]}
    conversion = params.get("conversion_type_params") or {}
    inputs = [params.get("numerator"), params.get("denominator"), *(params.get("metrics") or [])]
    inputs += [conversion.get("base_metric"), conversion.get("conversion_metric")]
    return set().union(*(semantic_models_of(i["name"], metrics) for i in inputs if i))


def expected_rows(manifest: dict, semantic_manifest: dict) -> dict[str, dict]:
    metrics = {m["name"]: m for m in semantic_manifest["metrics"]}
    files = {m["name"]: m["original_file_path"] for m in manifest["metrics"].values()}
    return {
        name: {
            "label": metric.get("label") or "",
            "type": metric["type"],
            "semantic models": semantic_models_of(name, metrics),
            "defined in": f"dbt/{files[name]}",
        }
        for name, metric in metrics.items()
    }


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def brief_rows(text: str) -> tuple[dict[str, dict], list[str]]:
    """The table under the heading, as {metric: row}; problems with its shape go in the second value."""
    lines = text.splitlines()
    if HEADING not in lines:
        return {}, [f"no '{HEADING}' section"]
    table = []
    for line in lines[lines.index(HEADING) + 1 :]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            table.append(line)
        elif table:
            break
    if len(table) < 2 or tuple(c.lower() for c in cells(table[0])) != COLUMNS:
        return {}, [f"the table under '{HEADING}' has no header | {' | '.join(COLUMNS)} |"]
    rows, found = {}, []
    for line in table[2:]:
        row = cells(line)
        name = CODE.fullmatch(row[0])
        if len(row) != len(COLUMNS) or not name:
            found.append(f"row {line!r}: not | `metric` | label | type | `models` | `file` |")
            continue
        if name.group(1) in rows:
            found.append(f"metric {name.group(1)}: two rows")
        rows[name.group(1)] = {
            "label": row[1],
            "type": row[2].strip("`"),
            "semantic models": set(CODE.findall(row[3])),
            "defined in": row[4].strip("`"),
        }
    return rows, found


def problems(expected: dict[str, dict], rows: dict[str, dict]) -> list[str]:
    found = [f"metric {name}: missing from the table" for name in sorted(expected.keys() - rows.keys())]
    found += [f"metric {name}: in the table, not in the project" for name in sorted(rows.keys() - expected.keys())]
    for name in sorted(expected.keys() & rows.keys()):
        for column, want in expected[name].items():
            got = rows[name][column]
            if got != want:
                show = (lambda v: ", ".join(sorted(v))) if isinstance(want, set) else str
                found.append(f"metric {name}: {column} is {show(got) or 'empty'}, the project says {show(want)}")
    return found


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "target")
    default = Path(__file__).resolve().parents[2] / "docs/target-architecture.md"
    brief = Path(sys.argv[2]) if len(sys.argv) > 2 else default
    manifest = json.loads((target / "manifest.json").read_text())
    semantic_manifest = json.loads((target / "semantic_manifest.json").read_text())
    expected = expected_rows(manifest, semantic_manifest)
    rows, found = brief_rows(brief.read_text())
    found += problems(expected, rows)
    for problem in found:
        print(f"check_brief: {problem}", file=sys.stderr)
    if not found:
        print(f"check_brief: {len(expected)} metrics in the brief's table, as the project defines them")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
