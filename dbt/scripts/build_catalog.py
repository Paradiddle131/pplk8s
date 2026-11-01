"""Write the agent catalog and the native data agent's authored context from the dbt manifests.

The semantic YAML and the model YAML are the single source of agent context (semantic/PLAN.md SL-3).
From `target/manifest.json` and `target/semantic_manifest.json` (after `dbt parse`) this writes, under
`target/catalog/`:

- `agent.json`: the catalog the metric toolset reads (S3): the public models (gold and exposed, SL-4)
  with their relation, pipelines, grain and column descriptions, and every metric with its label,
  description, type, pipelines, readiness products, time grain and the dimensions it can be grouped by,
  a categorical one with its known values when its column declares them (an `accepted_values` test), so the
  agent filters on a value the data holds instead of guessing one, and typed `numeric` when its column
  declares a numeric `data_type`, so the agent may compare it (MetricFlow knows only categorical and time).
  A metric's readiness products are the `ops.readiness` products of the models it reads,
  `<pipeline>.<layer>` (e.g. `sales.silver`), which is how the agent states its freshness (SL-4).
  And the glossary: the business terms that are not metrics, from `config.meta.glossary` on the models
  that hold them, each with the metrics and dimensions it maps to; and the saved queries (#164), each with
  its question (`config.meta.question`), metrics, group-bys, filters and readiness products.
- `data_agent/system_instruction.yaml`: the authored context of a BigQuery data agent, in the shape
  Google documents (a list of single-key maps: `system_instruction`, `tables` with fields and their
  aggregations from the simple metrics, `relationships` from the entities, `glossaries` from the metrics
  and the glossary terms,
  `additional_descriptions` from the derived and ratio metrics' formulas).
- `data_agent/example_queries.json`: the verified queries (`naturalLanguageQuestion`, `sqlQuery`): one per
  metric, the metric by day, and one per saved query, its question, each as MetricFlow compiles it.

The third artefact, the warehouse comments, is built by dbt itself: `persist_docs` on gold and exposed,
and the `semantic.metrics` and `semantic.glossary` models (models/semantic/).

Table names are `database.schema.table` of the dbt target, so a BigQuery target yields
`project.dataset.table` and the compiled SQL its dialect, with no change here.
MetricFlow resolves dimensions and compiles SQL without a warehouse connection.

Usage, from dbt/ with the image's pins: python scripts/build_catalog.py [target_dir]
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

LAYER_TAGS = {"bronze", "silver", "gold", "exposed", "semantic"}

SYSTEM_INSTRUCTION = (
    "You answer business questions about the data these tables describe. "
    "Compute a business figure only as its metric is defined in the glossary and the example queries; "
    "never invent another definition of a figure a metric defines. Dates are UTC days. "
    "A glossary term that is not a metric names the metrics and dimensions it maps to."
)


def _relation(database: str | None, schema: str, alias: str) -> str:
    return ".".join(part for part in (database, schema, alias) if part)


def _pipelines(tags: list[str]) -> list[str]:
    return sorted(tag for tag in tags if tag not in LAYER_TAGS)


def _grain(manifest: dict, unique_id: str) -> list[str]:
    """The model's grain, from the uniqueness test attached to it."""
    for node in manifest["nodes"].values():
        if node["resource_type"] != "test" or node.get("attached_node") != unique_id:
            continue
        test = node.get("test_metadata") or {}
        if test.get("name") == "unique":
            return [node["column_name"]]
        if test.get("name") == "unique_combination":
            return list(test["kwargs"]["columns"])
    return []


def public_models(manifest: dict) -> list[dict]:
    models = []
    for unique_id, node in sorted(manifest["nodes"].items()):
        if node["resource_type"] != "model" or node.get("access") != "public":
            continue
        layer = next((tag for tag in node["tags"] if tag in LAYER_TAGS), None)
        models.append(
            {
                "name": node["name"],
                "relation": _relation(node.get("database"), node["schema"], node["alias"]),
                "layer": layer,
                "group": node.get("group"),
                "pipelines": _pipelines(node["tags"]),
                "description": node["description"],
                "grain": _grain(manifest, unique_id),
                "columns": [
                    {"name": column["name"], "description": column["description"]}
                    for column in node["columns"].values()
                ],
            }
        )
    return models


def accepted_values(manifest: dict) -> dict[tuple[str, str], list[str]]:
    """The values each model column declares with an `accepted_values` test, by (model, column)."""
    found = {}
    for node in manifest["nodes"].values():
        test = node.get("test_metadata") or {}
        if node["resource_type"] == "test" and test.get("name") == "accepted_values" and node.get("attached_node"):
            model = manifest["nodes"][node["attached_node"]]["name"]
            found[(model, node["column_name"])] = [str(value) for value in test["kwargs"]["values"]]
    return found


# Postgres and BigQuery spellings of a number type, as a column's data_type declares it.
NUMERIC_TYPES = ("numeric", "decimal", "bignumeric", "integer", "int", "int64", "bigint", "smallint", "float64")


def numeric_columns(manifest: dict) -> set[tuple[str, str]]:
    """The model columns whose declared `data_type` is a number, by (model, column)."""
    return {
        (node["name"], name)
        for node in manifest["nodes"].values()
        if node["resource_type"] == "model"
        for name, column in node.get("columns", {}).items()
        if (column.get("data_type") or "").lower().split("(")[0].strip() in NUMERIC_TYPES
    }


def glossary(manifest: dict) -> list[dict]:
    """The business terms that are not metrics, from `config.meta.glossary` on the models that hold them."""
    terms = []
    for node in manifest["nodes"].values():
        if node["resource_type"] != "model":
            continue
        for entry in node["config"].get("meta", {}).get("glossary", []):
            terms.append(
                {
                    "term": entry.get("term", ""),
                    "description": " ".join(entry.get("description", "").split()),
                    "synonyms": entry.get("synonyms", []),
                    "metrics": entry.get("metrics", []),
                    "dimensions": entry.get("dimensions", []),
                    "model": node["name"],
                }
            )
    return sorted(terms, key=lambda term: term["term"].lower())


class SemanticIndex:
    """Lookups over the semantic manifest and the dbt manifest that several artefacts share."""

    def __init__(self, manifest: dict, semantic_manifest: dict) -> None:
        self.semantic_models = {model["name"]: model for model in semantic_manifest["semantic_models"]}
        self.metrics = sorted(semantic_manifest["metrics"], key=lambda metric: metric["name"])
        self.saved_queries = sorted(semantic_manifest.get("saved_queries", []), key=lambda query: query["name"])
        self._saved_query_meta = {
            node["name"]: node["config"].get("meta") or {} for node in manifest.get("saved_queries", {}).values()
        }
        self.tags_of_semantic_model = {}
        for node in manifest["semantic_models"].values():
            tags = [tag for node_id in node["depends_on"]["nodes"] for tag in manifest["nodes"][node_id]["tags"]]
            self.tags_of_semantic_model[node["name"]] = tags
        self.model_of_semantic_model = {
            node["name"]: manifest["nodes"][node["depends_on"]["nodes"][0]]["name"]
            for node in manifest["semantic_models"].values()
        }
        self.accepted_values = accepted_values(manifest)
        self.numeric_columns = numeric_columns(manifest)
        self._nodes = {**manifest["metrics"], **manifest["semantic_models"]}
        self._metric_ids = {node["name"]: unique_id for unique_id, node in manifest["metrics"].items()}

    def _semantic_model_names(self, unique_id: str) -> set[str]:
        """A simple metric depends on its semantic model, any other metric on the metrics it combines."""
        node = self._nodes[unique_id]
        if unique_id.startswith("semantic_model."):
            return {node["name"]}
        return set().union(*(self._semantic_model_names(parent) for parent in node["depends_on"]["nodes"]))

    def models_of_metric(self, metric: dict) -> list[dict]:
        names = self._semantic_model_names(self._metric_ids[metric["name"]])
        return [self.semantic_models[name] for name in sorted(names)]

    def pipelines(self, metric: dict) -> list[str]:
        tags = {tag for model in self.models_of_metric(metric) for tag in self.tags_of_semantic_model[model["name"]]}
        return _pipelines(sorted(tags))

    def readiness(self, metric: dict) -> list[str]:
        """The readiness products the metric's models are: `<pipeline>.<layer>`, as the DAGs record them."""
        products = set()
        for model in self.models_of_metric(metric):
            tags = self.tags_of_semantic_model[model["name"]]
            layers = [tag for tag in tags if tag in LAYER_TAGS]
            products |= {f"{pipeline}.{layer}" for pipeline in _pipelines(tags) for layer in layers}
        return sorted(products)

    def time_grain(self, metric: dict) -> str | None:
        grains = set()
        for model in self.models_of_metric(metric):
            time_dimension = model["defaults"]["agg_time_dimension"]
            for dimension in model["dimensions"]:
                if dimension["name"] == time_dimension:
                    grains.add(dimension["type_params"]["time_granularity"])
        return grains.pop() if len(grains) == 1 else None

    def known_values(self, semantic_model: str, column: str) -> list[str] | None:
        """The values a dimension's column declares, or None when it declares none."""
        return self.accepted_values.get((self.model_of_semantic_model.get(semantic_model, ""), column))

    def is_numeric(self, semantic_model: str, column: str) -> bool:
        """Whether a dimension's column declares a numeric data_type."""
        return (self.model_of_semantic_model.get(semantic_model, ""), column) in self.numeric_columns

    def question(self, saved_query: dict) -> str:
        """The business question a saved query answers, from its `config.meta.question`."""
        return (self._saved_query_meta.get(saved_query["name"], {}).get("question") or "").strip()

    @staticmethod
    def table(model: dict) -> str:
        relation = model["node_relation"]
        return _relation(relation.get("database"), relation["schema_name"], relation["alias"])


def group_by_name(item: str) -> str:
    """A saved query's group-by as query_metrics names it: `Dimension('order__status')` is `order__status`,
    `TimeDimension('metric_time', 'day')` is `metric_time__day`."""
    found = re.fullmatch(r"\s*(?:Time)?Dimension\(\s*'(\w+)'\s*(?:,\s*'(\w+)'\s*)?\)\s*", item)
    if not found:
        raise ValueError(f"saved query group-by {item!r}: only Dimension(...) and TimeDimension(...) are supported")
    name, grain = found.groups()
    return f"{name}__{grain}" if grain else name


def saved_queries(index: SemanticIndex) -> list[dict]:
    metrics = {metric["name"]: metric for metric in index.metrics}
    found = []
    for query in index.saved_queries:
        params = query["query_params"]
        names = list(params["metrics"])
        found.append(
            {
                "name": query["name"],
                "label": query.get("label") or query["name"],
                "description": query.get("description") or "",
                "question": index.question(query),
                "metrics": names,
                "group_by": [group_by_name(item) for item in params.get("group_by") or []],
                "where": [item["where_sql_template"] for item in (params.get("where") or {}).get("where_filters", [])],
                "readiness": sorted({p for name in names for p in index.readiness(metrics[name])}),
            }
        )
    return found


def agent_catalog(manifest: dict, index: SemanticIndex, dimensions: Callable[[str], list[dict]]) -> dict:
    return {
        "models": public_models(manifest),
        "glossary": glossary(manifest),
        "metrics": [
            {
                "name": metric["name"],
                "label": metric["label"],
                "description": metric["description"],
                "type": metric["type"],
                "pipelines": index.pipelines(metric),
                "readiness": index.readiness(metric),
                "time_grain": index.time_grain(metric),
                "semantic_models": [model["name"] for model in index.models_of_metric(metric)],
                "dimensions": dimensions(metric["name"]),
            }
            for metric in index.metrics
        ],
        "saved_queries": saved_queries(index),
    }


def _item(**fields: object) -> list[dict]:
    """The documented authored-context form: every property is a single-key map in a list."""
    return [{key: value} for key, value in fields.items() if value not in (None, [], "")]


def _primary_key(model: dict) -> str:
    entity = next(entity for entity in model["entities"] if entity["type"] == "primary")
    return entity.get("expr") or entity["name"]


def system_instruction(index: SemanticIndex, terms: list[dict]) -> list[dict]:
    aggregations: dict[str, dict[str, list[str]]] = {name: {} for name in index.semantic_models}
    for metric in index.metrics:
        params = metric["type_params"]["metric_aggregation_params"]
        if params is None:
            continue
        model = index.semantic_models[params["semantic_model"]]
        # A row count (`expr: 1`) is a count of the primary key, which is never NULL.
        field = metric["type_params"]["expr"]
        field = _primary_key(model) if field == "1" else field
        aggregation = params["agg"].replace("count_distinct", "count distinct")
        if aggregation not in aggregations[model["name"]].setdefault(field, []):
            aggregations[model["name"]][field].append(aggregation)

    tables = []
    for model in index.semantic_models.values():
        fields = aggregations[model["name"]]
        tables.append(
            {
                "table": _item(
                    name=index.table(model),
                    fields=[{"field": _item(name=name, aggregations=aggs)} for name, aggs in sorted(fields.items())],
                )
            }
        )

    relationships = []
    primaries = {
        entity["name"]: (model, entity)
        for model in index.semantic_models.values()
        for entity in model["entities"]
        if entity["type"] in ("primary", "unique", "natural")
    }
    for model in index.semantic_models.values():
        for entity in model["entities"]:
            if entity["type"] != "foreign" or entity["name"] not in primaries:
                continue
            other, key = primaries[entity["name"]]
            relationships.append(
                {
                    "relationship": _item(
                        name=f"{model['name']}_to_{other['name']}",
                        description=(
                            f"Each {model['name']} row belongs to at most one {other['name']} row, "
                            f"by the {entity['name']} entity."
                        ),
                        relationship_type="many-to-one",
                        join_type="left",
                        left_table=index.table(model),
                        right_table=index.table(other),
                        relationship_columns=_item(
                            left_column=entity.get("expr") or entity["name"],
                            right_column=key.get("expr") or key["name"],
                        ),
                    )
                }
            )

    labels = {metric["name"]: metric["label"] for metric in index.metrics}
    glossaries = [
        {"glossary": _item(term=metric["label"], description=metric["description"], synonyms=[metric["name"]])}
        for metric in index.metrics
    ]
    for term in terms:
        # The data agent's glossary has no field for a mapping, so the term's description names it.
        mapping = []
        if term["metrics"]:
            mapping.append(f"Metrics: {', '.join(labels.get(name, name) for name in term['metrics'])}.")
        if term["dimensions"]:
            mapping.append(f"Dimensions: {', '.join(term['dimensions'])}.")
        description = " ".join([term["description"], *mapping])
        glossaries.append({"glossary": _item(term=term["term"], description=description, synonyms=term["synonyms"])})

    descriptions = []
    for metric in index.metrics:
        params = metric["type_params"]
        if metric["type"] == "derived":
            # The formula in words: a coalesce or nullif that only guards a missing input or a zero, and a
            # cast to a decimal, say nothing to a reader; an input taken a period earlier says so.
            words = dict(labels)
            for item in params["metrics"]:
                offset = item.get("offset_window")
                if item.get("alias") and offset:
                    words[item["alias"]] = f"{labels[item['name']]} {offset['count']} {offset['granularity']} earlier"
            formula = re.sub(r"(?:coalesce\((\w+), 0\)|nullif\((\w+), 0\))", lambda m: m[1] or m[2], params["expr"])
            formula = formula.replace(" * 1.0", "")
            formula = re.sub(r"\b\w+\b", lambda m, words=words: words.get(m[0], m[0]), formula)
            descriptions.append({"text": f"{metric['label']} = {formula}."})
        elif metric["type"] == "cumulative":
            params = params["cumulative_type_params"]
            window = params.get("window")
            if params.get("grain_to_date"):
                span = f"from the start of the {params['grain_to_date']}"
            elif window:
                span = f"over the trailing {window['count']} {window['granularity']}"
            else:
                span = "over all time"
            descriptions.append({"text": f"{metric['label']} = {labels[params['metric']['name']]} summed {span}."})
        elif metric["type"] == "ratio":
            numerator, denominator = params["numerator"]["name"], params["denominator"]["name"]
            descriptions.append({"text": f"{metric['label']} = {labels[numerator]} / {labels[denominator]}."})

    return _item(
        system_instruction=SYSTEM_INSTRUCTION,
        tables=tables,
        relationships=relationships,
        glossaries=glossaries,
        additional_descriptions=descriptions,
    )


def example_queries(
    index: SemanticIndex, compiled_sql: Callable[[str], str], compiled_saved_query: Callable[[str], str]
) -> list[dict]:
    """The data agent's verified queries: each metric by day, then each saved query with its question."""
    by_metric = [
        {
            "naturalLanguageQuestion": f"What is {metric['label'][0].lower() + metric['label'][1:]} by day?",
            "sqlQuery": compiled_sql(metric["name"]),
        }
        for metric in index.metrics
    ]
    by_saved_query = [
        {"naturalLanguageQuestion": index.question(query), "sqlQuery": compiled_saved_query(query["name"])}
        for query in index.saved_queries
    ]
    return by_metric + by_saved_query


def _metricflow(
    project_dir: Path, index: SemanticIndex
) -> tuple[Callable[[str], list[dict]], Callable[[str], str], Callable[[str], str]]:
    """Dimensions and compiled SQL, of a metric and of a saved query, from MetricFlow's engine, set up as the
    mf CLI sets it up."""
    from dbt_metricflow.cli.cli_configuration import CLIConfiguration
    from metricflow.engine.metricflow_engine import MetricFlowEngine, MetricFlowQueryRequest

    config = CLIConfiguration()
    config.setup(dbt_project_path=project_dir)
    engine = MetricFlowEngine(semantic_manifest_lookup=config.semantic_manifest_lookup, sql_client=config.sql_client)

    def dimensions(metric: str) -> list[dict]:
        found = []
        for dimension in engine.simple_dimensions_for_metrics([metric]):
            name = dimension.granularity_free_dunder_name
            description = dimension.description
            if name == "metric_time":
                description = "The metric's own time dimension; group by metric_time__day, __week, __month or __year."
            entry = {"name": name, "type": dimension.type.value, "description": description}
            if dimension.type.value == "categorical" and dimension.semantic_model_reference is not None:
                # A dimension's column is its expr when that is a plain column name, else its own name.
                column = dimension.expr if dimension.expr and dimension.expr.isidentifier() else dimension.name
                semantic_model = dimension.semantic_model_reference.semantic_model_name
                values = index.known_values(semantic_model, column)
                if values is not None:
                    entry["values"] = values
                if index.is_numeric(semantic_model, column):
                    entry["type"] = "numeric"
            found.append(entry)
        return sorted(found, key=lambda dimension: dimension["name"])

    def compiled_sql(metric: str) -> str:
        request = MetricFlowQueryRequest.create(
            metric_names=[metric], group_by_names=["metric_time__day"], order_by_names=["metric_time__day"]
        )
        return engine.explain(request).sql_statement.sql

    def compiled_saved_query(name: str) -> str:
        return engine.explain(MetricFlowQueryRequest.create(saved_query_name=name)).sql_statement.sql

    return dimensions, compiled_sql, compiled_saved_query


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "target")
    manifest = json.loads((target / "manifest.json").read_text())
    index = SemanticIndex(manifest, json.loads((target / "semantic_manifest.json").read_text()))
    dimensions, compiled_sql, compiled_saved_query = _metricflow(Path(__file__).resolve().parents[1], index)

    out = target / "catalog"
    (out / "data_agent").mkdir(parents=True, exist_ok=True)
    catalog = agent_catalog(manifest, index, dimensions)
    (out / "agent.json").write_text(json.dumps(catalog, indent=2) + "\n")
    (out / "data_agent" / "system_instruction.yaml").write_text(
        yaml.safe_dump(system_instruction(index, catalog["glossary"]), sort_keys=False, allow_unicode=True, width=110)
    )
    (out / "data_agent" / "example_queries.json").write_text(
        json.dumps(example_queries(index, compiled_sql, compiled_saved_query), indent=2) + "\n"
    )
    print(
        f"build_catalog: {len(catalog['models'])} public models, {len(catalog['metrics'])} metrics "
        f"and {len(catalog['glossary'])} glossary terms in {out}; {len(catalog['saved_queries'])} saved queries"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
