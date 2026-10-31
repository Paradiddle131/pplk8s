"""Fail when the catalog artefacts of build_catalog.py miss a public model or a metric, or stray from their shape.

Checks, against the manifests the artefacts were built from (semantic/PLAN.md SL-3, SL-4):
- agent.json lists exactly the public models and every metric; every public model and every one of its
  columns is described (persist_docs turns the words into warehouse comments);
- system_instruction.yaml parses and uses only the keys Google documents for a BigQuery data agent's
  authored context, with the documented relationship and join types;
- example_queries.json holds one verified query per metric and one per saved query, with the documented keys only;
- agent.json lists every saved query with its question, metrics and group-bys (#164);
- every glossary term (`config.meta.glossary` on a model) is in agent.json, has a description, maps to at
  least one metric or dimension, names only metrics the semantic manifest defines and dimensions one of its
  metrics groups by, and neither repeats another term nor a metric's name or label (a metric is its own
  glossary entry).

Usage: python scripts/check_catalog.py [target_dir]  (after build_catalog.py)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# Documented authored-context keys: each container key maps to the keys its items may hold.
AUTHORED_CONTEXT_KEYS = {
    None: {"system_instruction", "tables", "relationships", "glossaries", "additional_descriptions"},
    "tables": {"table"},
    "table": {"name", "fields"},
    "fields": {"field"},
    "field": {"name", "aggregations"},
    "relationships": {"relationship"},
    "relationship": {
        "name",
        "description",
        "relationship_type",
        "join_type",
        "left_table",
        "right_table",
        "relationship_columns",
    },
    "relationship_columns": {"left_column", "right_column"},
    "glossaries": {"glossary"},
    "glossary": {"term", "description", "synonyms"},
    "additional_descriptions": {"text"},
}
ENUMS = {
    "relationship_type": {"one-to-one", "one-to-many", "many-to-one", "many-to-many"},
    "join_type": {"inner", "outer", "left", "right", "full"},
}
EXAMPLE_QUERY_KEYS = {"naturalLanguageQuestion", "sqlQuery", "parameters"}
GLOSSARY_KEYS = {"term", "description", "synonyms", "metrics", "dimensions"}


def _key(term: str) -> str:
    """A term as a reader matches it: case, spacing and a plural s do not make another term."""
    return " ".join(term.lower().split()).removesuffix("s")


def glossary_problems(manifest: dict, catalog: dict) -> list[str]:
    metrics = {metric["name"]: metric for metric in catalog["metrics"]}
    taken = {_key(name): f"metric {name}" for name in metrics}
    taken |= {_key(metric["label"]): f"metric {name}" for name, metric in metrics.items()}
    dimensions = {name: {d["name"] for d in metric["dimensions"]} for name, metric in metrics.items()}
    found, count = [], 0
    for node in sorted(manifest["nodes"].values(), key=lambda n: n["name"]):
        if node["resource_type"] != "model":
            continue
        for entry in node["config"].get("meta", {}).get("glossary", []):
            count += 1
            term = entry.get("term") or "?"
            where = f"glossary term {term!r} on {node['name']}"
            found += [f"{where}: unknown key {key!r}" for key in sorted(entry.keys() - GLOSSARY_KEYS)]
            if not (entry.get("description") or "").strip():
                found.append(f"{where}: no description")
            named_metrics, named_dimensions = entry.get("metrics", []), entry.get("dimensions", [])
            if not named_metrics and not named_dimensions:
                found.append(f"{where}: maps to no metric or dimension")
            found += [f"{where}: unknown metric {name}" for name in named_metrics if name not in metrics]
            reachable = set().union(*(dimensions[name] for name in named_metrics or metrics if name in dimensions))
            found += [
                f"{where}: dimension {name} is not a dimension of {'its metrics' if named_metrics else 'any metric'}"
                for name in named_dimensions
                if name not in reachable
            ]
            if _key(term) in taken:
                found.append(f"{where}: repeats {taken[_key(term)]}")
            taken.setdefault(_key(term), where)
    if len(catalog.get("glossary", [])) != count:
        found.append(f"agent.json: {len(catalog.get('glossary', []))} glossary terms for {count} in the manifest")
    return found


def authored_context_problems(document: object, parent: str | None = None, path: str = "") -> list[str]:
    """Walk the documented form: a list of single-key maps at every level."""
    if not isinstance(document, list):
        return [f"{path or 'document'}: expected a list of single-key maps"]
    found = []
    for position, item in enumerate(document):
        where = f"{path}[{position}]"
        if not isinstance(item, dict) or len(item) != 1:
            found.append(f"{where}: expected a single-key map")
            continue
        ((key, value),) = item.items()
        if key not in AUTHORED_CONTEXT_KEYS[parent]:
            found.append(f"{where}: undocumented key {key!r} under {parent or 'the root'}")
        elif key in AUTHORED_CONTEXT_KEYS:
            found += authored_context_problems(value, key, f"{where}.{key}")
        elif key in ENUMS and value not in ENUMS[key]:
            found.append(f"{where}.{key}: {value!r} is not one of {sorted(ENUMS[key])}")
        elif not (isinstance(value, str) or (isinstance(value, list) and all(isinstance(v, str) for v in value))):
            found.append(f"{where}.{key}: expected text or a list of text")
    return found


def problems(target: Path) -> list[str]:
    manifest = json.loads((target / "manifest.json").read_text())
    semantic_manifest = json.loads((target / "semantic_manifest.json").read_text())
    catalog_dir = target / "catalog"
    catalog = json.loads((catalog_dir / "agent.json").read_text())
    found = []

    public = {
        node["name"]: node
        for node in manifest["nodes"].values()
        if node["resource_type"] == "model" and node.get("access") == "public"
    }
    if not public:
        found.append("no public models in the manifest")
    listed = {model["name"] for model in catalog["models"]}
    found += [f"agent.json: public model {name} missing" for name in sorted(public.keys() - listed)]
    found += [f"agent.json: {name} is listed but not public" for name in sorted(listed - public.keys())]
    for name, node in sorted(public.items()):
        if not node["description"].strip():
            found.append(f"public model {name}: no description")
        found += [
            f"public model {name}: column {column} has no description"
            for column, spec in node["columns"].items()
            if not (spec.get("description") or "").strip()
        ]

    metrics = sorted(metric["name"] for metric in semantic_manifest["metrics"])
    if sorted(metric["name"] for metric in catalog["metrics"]) != metrics:
        found.append(f"agent.json: metrics {sorted(m['name'] for m in catalog['metrics'])} != manifest {metrics}")
    found += [
        f"agent.json: metric {metric['name']} has no {field}"
        for metric in catalog["metrics"]
        for field in ("pipelines", "readiness", "dimensions", "time_grain")
        if not metric.get(field)
    ]

    found += glossary_problems(manifest, catalog)

    context = yaml.safe_load((catalog_dir / "data_agent" / "system_instruction.yaml").read_text())
    found += [f"system_instruction.yaml: {problem}" for problem in authored_context_problems(context)]

    saved = sorted(query["name"] for query in semantic_manifest.get("saved_queries", []))
    listed_saved = {query["name"]: query for query in catalog.get("saved_queries", [])}
    if sorted(listed_saved) != saved:
        found.append(f"agent.json: saved queries {sorted(listed_saved)} != manifest {saved}")
    found += [
        f"agent.json: saved query {name} has no {field}"
        for name, query in sorted(listed_saved.items())
        for field in ("question", "metrics", "readiness")
        if not query.get(field)
    ]

    queries = json.loads((catalog_dir / "data_agent" / "example_queries.json").read_text())
    if len(queries) != len(metrics) + len(saved):
        found.append(
            f"example_queries.json: {len(queries)} queries for {len(metrics)} metrics and {len(saved)} saved queries"
        )
    for position, query in enumerate(queries):
        required = {"naturalLanguageQuestion", "sqlQuery"}
        if not isinstance(query, dict) or not required <= query.keys() <= EXAMPLE_QUERY_KEYS:
            found.append(f"example_queries.json[{position}]: keys must be {sorted(EXAMPLE_QUERY_KEYS)}")
    return found


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "target")
    found = problems(target)
    for problem in found:
        print(f"check_catalog: {problem}", file=sys.stderr)
    if not found:
        print(
            "check_catalog: every public model, metric, glossary term and saved query is catalogued; "
            "the authored context uses documented keys"
        )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
