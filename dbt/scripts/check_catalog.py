"""Fail when the catalog artefacts of build_catalog.py miss a public model or a metric, or stray from their shape.

Checks, against the manifests the artefacts were built from (semantic/PLAN.md SL-3, SL-4):
- agent.json lists exactly the public models and every metric; every public model and every one of its
  columns is described (persist_docs turns the words into warehouse comments);
- system_instruction.yaml parses and uses only the keys Google documents for a BigQuery data agent's
  authored context, with the documented relationship and join types, and no `glossaries`, which the structured
  context carries;
- context.json is a valid v1 `Context` of the Conversational Analytics API, against the pinned copy of its
  schemas (scripts/schemas/, from the API's discovery document; scripts/pin_context_schema.py renews it): no
  key the schema lacks, every field it calls "Required.", every text within its "at most N bytes", nothing
  output-only or deprecated; it names every table the semantic models and the time spine read, holds one
  glossary term per metric and per glossary term, the same example queries as example_queries.json and
  system_instruction.yaml as its `systemInstruction`;
- no table carries more than 10 glossary terms (build_catalog.glossary_tables), the most a data agent reads
  from Knowledge Catalog per table;
- example_queries.json holds one verified query per metric and one per saved query, with the documented keys only;
- agent.json lists every saved query with its question, metrics and group-bys (#164);
- agent.json lists every semantic model with its table and readiness products (#207);
- every glossary term (`config.meta.glossary` on a model) is in agent.json, has a description, maps to at
  least one metric or dimension, names only metrics the semantic manifest defines and dimensions one of its
  metrics groups by, and neither repeats another term nor a metric's name or label (a metric is its own
  glossary entry).

Usage: python scripts/check_catalog.py [target_dir]  (after build_catalog.py)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml
from build_catalog import GLOSSARY_TERMS_PER_TABLE, SemanticIndex, glossary, glossary_tables

CONTEXT_SCHEMA = Path(__file__).resolve().parent / "schemas" / "geminidataanalytics-v1-context.json"
REQUIRED = re.compile(r"\s*Required\.")
AT_MOST_BYTES = re.compile(r"[Mm]ust be at most ([\d,]+) bytes")

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


def schema_problems(value: object, spec: dict, schemas: dict, path: str = "") -> list[str]:
    """Walk a value against a discovery-document schema: `$ref`, `type`, `items` and `properties`."""
    if "$ref" in spec:
        if spec["$ref"] not in schemas:
            return [f"{path or 'the root'}: {spec['$ref']} is not in the pinned schema"]
        return schema_problems(value, schemas[spec["$ref"]], schemas, path)
    kind = spec.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return [f"{path or 'the root'}: expected an object"]
        properties = spec.get("properties", {})
        found = [f"{path or 'the root'}: unknown key {key!r}" for key in sorted(value.keys() - properties.keys())]
        for key, prop in properties.items():
            where = f"{path}.{key}" if path else key
            if value.get(key) in (None, "", [], {}):
                if REQUIRED.match(prop.get("description", "")):
                    found.append(f"{where}: required")
                continue
            if prop.get("readOnly") or prop.get("deprecated"):
                found.append(f"{where}: {'output only' if prop.get('readOnly') else 'deprecated'}")
            found += schema_problems(value[key], prop, schemas, where)
        return found
    if kind == "array":
        if not isinstance(value, list):
            return [f"{path}: expected a list"]
        return [
            problem
            for i, item in enumerate(value)
            for problem in schema_problems(item, spec["items"], schemas, f"{path}[{i}]")
        ]
    if kind == "string":
        if not isinstance(value, str):
            return [f"{path}: expected text"]
        bound = AT_MOST_BYTES.search(spec.get("description", ""))
        if bound and len(value.encode()) > int(bound[1].replace(",", "")):
            return [f"{path}: {len(value.encode())} bytes, more than {bound[1]}"]
        return []
    if kind in ("boolean", "integer", "number"):
        types = {"boolean": bool, "integer": int, "number": (int, float)}[kind]
        return [] if isinstance(value, types) else [f"{path}: expected a {kind}"]
    return [f"{path}: schema type {kind!r} is not handled"]


def context_problems(manifest: dict, semantic_manifest: dict, catalog: dict, data_agent: Path) -> list[str]:
    """context.json against the pinned v1 schema and the other artefacts, and the glossary terms per table."""
    pin = json.loads(CONTEXT_SCHEMA.read_text())
    context = json.loads((data_agent / "context.json").read_text())
    found = schema_problems(context, {"$ref": pin["root"]}, pin["schemas"])

    index = SemanticIndex(manifest, semantic_manifest)
    tables = {
        ".".join(part for part in (ref.get("projectId"), ref.get("datasetId"), ref.get("tableId")) if part)
        for ref in ((context.get("datasourceReferences") or {}).get("bq") or {}).get("tableReferences", [])
    }
    expected = {index.table(model) for model in index.semantic_models.values()}
    expected |= {SemanticIndex.table(spine) for spine in index.time_spines}
    found += [f"table {table} missing" for table in sorted(expected - tables)]

    names = [metric["label"] for metric in catalog["metrics"]] + [term["term"] for term in catalog["glossary"]]
    listed = [term.get("displayName", "") for term in context.get("glossaryTerms", [])]
    found += [f"glossary term {name!r} missing" for name in sorted(set(names) - set(listed))]
    found += [
        f"glossaryTerms[{i}] {name!r} is no metric or glossary term"
        for i, name in enumerate(listed)
        if name not in names
    ]
    if len(listed) != len(names):
        found.append(f"{len(listed)} glossary terms for {len(names)} metrics and glossary terms")
    if context.get("exampleQueries") != json.loads((data_agent / "example_queries.json").read_text()):
        found.append("exampleQueries differ from example_queries.json")
    if context.get("systemInstruction") != (data_agent / "system_instruction.yaml").read_text():
        found.append("systemInstruction differs from system_instruction.yaml")
    found = [f"context.json: {problem}" for problem in found]

    # From the manifest, the generator's own source, so a term added there counts before agent.json holds it.
    for table, terms in glossary_tables(manifest, index, glossary(manifest)).items():
        if len(terms) > GLOSSARY_TERMS_PER_TABLE:
            found.append(
                f"table {table}: {len(terms)} glossary terms ({', '.join(terms)}); "
                f"a data agent reads at most {GLOSSARY_TERMS_PER_TABLE} per table"
            )
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
    if isinstance(context, list) and any(isinstance(item, dict) and "glossaries" in item for item in context):
        found.append("system_instruction.yaml: glossaries belong in context.json's glossaryTerms")

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

    models = sorted(model["name"] for model in semantic_manifest["semantic_models"])
    listed_models = {model["name"]: model for model in catalog.get("semantic_models", [])}
    if sorted(listed_models) != models:
        found.append(f"agent.json: semantic models {sorted(listed_models)} != manifest {models}")
    found += [
        f"agent.json: semantic model {name} has no {field}"
        for name, model in sorted(listed_models.items())
        for field in ("relation", "readiness")
        if not model.get(field)
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

    found += context_problems(manifest, semantic_manifest, catalog, catalog_dir / "data_agent")
    return found


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "target")
    found = problems(target)
    for problem in found:
        print(f"check_catalog: {problem}", file=sys.stderr)
    if not found:
        print(
            "check_catalog: every public model, metric, glossary term and saved query is catalogued; "
            "the authored context uses documented keys; context.json is a valid v1 Context"
        )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
