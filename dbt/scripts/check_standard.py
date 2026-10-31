"""Fail when the dbt project strays from the agent-ready warehouse standard (docs/agent-ready-warehouse.md).

Checks, offline against the manifests `dbt parse` writes (semantic/PLAN.md SL-3, SL-4):
- naming: every model sits in a layer folder and builds in that layer's schema; a bronze, silver, gold,
  exposed or legacy model carries the layer's prefix and its relation is the name without it; models, columns,
  semantic models, their entities and dimensions, and metrics are snake case;
- trust: gold and exposed models, and only they, are public in the analytics group, each with an enforced
  contract that types every column; semantic models sit on silver, so an agent reaches silver only through
  a metric;
- words: every model that builds a relation is described, every public model's column too, every
  semantic model with its entities, dimensions and measures, and every metric has a description and a label;
  every saved query a description, a label and the business question it answers (`config.meta.question`),
  which becomes its verified query's question.

Usage: python scripts/check_standard.py [target_dir]  (after `dbt parse`)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PREFIXES = {"bronze": "brz_", "silver": "slv_", "gold": "gld_", "exposed": "exp_", "legacy": "lgc_"}
LAYERS = (*PREFIXES, "semantic", "migration")
PUBLIC_LAYERS = {"gold", "exposed"}
PUBLIC_GROUP = "analytics"
SNAKE = re.compile(r"_?[a-z][a-z0-9_]*")


def described(item: dict) -> bool:
    return bool((item.get("description") or "").strip())


def model_problems(node: dict) -> list[str]:
    name, found = node["name"], []
    parts = Path(node["original_file_path"]).parts
    layer = parts[1] if len(parts) > 2 else None
    if layer not in LAYERS:
        return [f"model {name}: in {'/'.join(parts[:-1])}, not a layer folder ({', '.join(LAYERS)})"]
    if node["schema"] != layer:
        found.append(f"model {name}: builds in schema {node['schema']}, not its layer {layer}")
    if not SNAKE.fullmatch(name):
        found.append(f"model {name}: name is not snake case")
    prefix = PREFIXES.get(layer)
    ephemeral = node["config"].get("materialized") == "ephemeral"
    if prefix and not name.startswith(prefix):
        found.append(f"model {name}: in {layer}, so its name starts with {prefix}")
    elif prefix and not ephemeral and node["alias"] != name.removeprefix(prefix):
        found.append(f"model {name}: relation {node['alias']}, not the name without its prefix")
    elif not prefix and name.startswith(tuple(PREFIXES.values())):
        found.append(f"model {name}: in {layer}, so its name carries no layer prefix")
    found += [
        f"model {name}: column {column} is not snake case" for column in node["columns"] if not SNAKE.fullmatch(column)
    ]

    public = node.get("access") == "public"
    if public != (layer in PUBLIC_LAYERS):
        found.append(f"model {name}: {node.get('access')} in {layer}; only gold and exposed are public")
    if public and node.get("group") != PUBLIC_GROUP:
        found.append(f"model {name}: public outside the {PUBLIC_GROUP} group")
    if public and not node["config"].get("contract", {}).get("enforced"):
        found.append(f"public model {name}: no enforced contract")
    if not ephemeral and not described(node):
        found.append(f"{'public ' if public else ''}model {name}: no description")
    if public:
        found += [
            f"public model {name}: column {column} has no description"
            for column, spec in node["columns"].items()
            if not described(spec)
        ]
        found += [
            f"public model {name}: column {column} has no data_type"
            for column, spec in node["columns"].items()
            if not (spec.get("data_type") or "").strip()
        ]
    return found


def semantic_problems(semantic_manifest: dict) -> list[str]:
    found = []
    for model in sorted(semantic_manifest.get("semantic_models", []), key=lambda m: m["name"]):
        name = model["name"]
        if not SNAKE.fullmatch(name):
            found.append(f"semantic model {name}: name is not snake case")
        if not described(model):
            found.append(f"semantic model {name}: no description")
        if model["node_relation"]["schema_name"] != "silver":
            found.append(f"semantic model {name}: sits on {model['node_relation']['schema_name']}, not silver")
        for kind, noun in (("entities", "entity"), ("dimensions", "dimension"), ("measures", "measure")):
            for element in model.get(kind) or []:
                if not SNAKE.fullmatch(element["name"]):
                    found.append(f"semantic model {name}: {noun} {element['name']} is not snake case")
                if not described(element):
                    found.append(f"semantic model {name}: {noun} {element['name']} has no description")
    metrics = semantic_manifest.get("metrics", [])
    if not metrics:
        found.append("no metrics in the semantic manifest")
    for metric in sorted(metrics, key=lambda m: m["name"]):
        if not SNAKE.fullmatch(metric["name"]):
            found.append(f"metric {metric['name']}: name is not snake case")
        found += [
            f"metric {metric['name']}: no {field}"
            for field in ("description", "label")
            if not (metric.get(field) or "").strip()
        ]
    return found


def saved_query_problems(manifest: dict) -> list[str]:
    found = []
    for query in sorted(manifest.get("saved_queries", {}).values(), key=lambda q: q["name"]):
        name = query["name"]
        if not SNAKE.fullmatch(name):
            found.append(f"saved query {name}: name is not snake case")
        found += [
            f"saved query {name}: no {field}"
            for field in ("description", "label")
            if not (query.get(field) or "").strip()
        ]
        if not str((query["config"].get("meta") or {}).get("question") or "").strip():
            found.append(f"saved query {name}: no config.meta.question")
    return found


def problems(manifest: dict, semantic_manifest: dict) -> list[str]:
    models = sorted((n for n in manifest["nodes"].values() if n["resource_type"] == "model"), key=lambda n: n["name"])
    found = [problem for node in models for problem in model_problems(node)]
    return found + semantic_problems(semantic_manifest) + saved_query_problems(manifest)


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "target")
    manifest = json.loads((target / "manifest.json").read_text())
    semantic_manifest = json.loads((target / "semantic_manifest.json").read_text())
    found = problems(manifest, semantic_manifest)
    for problem in found:
        print(f"check_standard: {problem}", file=sys.stderr)
    if not found:
        models = [n for n in manifest["nodes"].values() if n["resource_type"] == "model"]
        public = sum(n.get("access") == "public" for n in models)
        print(
            f"check_standard: {len(models)} models named by layer; {public} public models, "
            f"{len(semantic_manifest['semantic_models'])} semantic models, "
            f"{len(semantic_manifest['metrics'])} metrics and "
            f"{len(manifest.get('saved_queries', {}))} saved queries described"
        )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
