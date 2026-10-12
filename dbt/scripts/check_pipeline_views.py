"""Fail when a view reads a model owned by another pipeline (PLAN.md D20, issue #27).

dbt-postgres rebuilds a table or view by renaming the old relation and dropping it with CASCADE,
and Postgres then drops every view that depends on it.  A view that reads another pipeline's model
would therefore vanish whenever that pipeline rebuilds its stage, so such a model must be a table.

Usage: python scripts/check_pipeline_views.py [target/manifest.json]  (after `dbt parse`)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LAYER_TAGS = {"bronze", "silver", "gold", "exposed"}


def pipeline(node: dict) -> str | None:
    owners = sorted(set(node["tags"]) - LAYER_TAGS)
    return owners[0] if len(owners) == 1 else None


def violations(manifest: dict) -> list[str]:
    models = {k: v for k, v in manifest["nodes"].items() if v["resource_type"] == "model"}
    problems = []
    for _, node in sorted(models.items()):
        owner = pipeline(node)
        if owner is None:
            problems.append(f"{node['name']}: needs exactly one pipeline tag, has {node['tags']}")
            continue
        if node["config"]["materialized"] != "view":
            continue
        for parent in node["depends_on"]["nodes"]:
            if parent in models and pipeline(models[parent]) != owner:
                problems.append(
                    f"{node['name']} ({owner}) is a view on {models[parent]['name']} "
                    f"({pipeline(models[parent])}); materialize it as a table"
                )
    return problems


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "target/manifest.json")
    problems = violations(json.loads(path.read_text()))
    for problem in problems:
        print(f"check_pipeline_views: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
