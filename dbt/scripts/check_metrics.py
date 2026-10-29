"""Fail when a metric or a semantic model lacks a description, or a metric lacks a label.

The semantic YAML is the single source of the agent catalog and the warehouse comments
(semantic/PLAN.md SL-3), so a metric without words is a metric the agent cannot explain.

Usage: python scripts/check_metrics.py [target/semantic_manifest.json]  (after `dbt parse`)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def problems(semantic_manifest: dict) -> list[str]:
    found = []
    for model in sorted(semantic_manifest.get("semantic_models", []), key=lambda m: m["name"]):
        if not (model.get("description") or "").strip():
            found.append(f"semantic model {model['name']}: no description")
    metrics = semantic_manifest.get("metrics", [])
    if not metrics:
        found.append("no metrics in the semantic manifest")
    for metric in sorted(metrics, key=lambda m: m["name"]):
        for field in ("description", "label"):
            if not (metric.get(field) or "").strip():
                found.append(f"metric {metric['name']}: no {field}")
    return found


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "target/semantic_manifest.json")
    found = problems(json.loads(path.read_text()))
    for problem in found:
        print(f"check_metrics: {problem}", file=sys.stderr)
    if not found:
        print(f"check_metrics: {len(json.loads(path.read_text())['metrics'])} metrics described and labelled")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
