"""Write the agent catalog and the native data agent's authored context from the dbt manifests.

The semantic YAML and the model YAML are the single source of agent context (semantic/PLAN.md SL-3).
From `target/manifest.json` and `target/semantic_manifest.json` (after `dbt parse`) this writes, under
`target/catalog/`:

- `agent.json`: the catalog the metric toolset reads (S3): the public models (gold and exposed, SL-4)
  with their relation, pipelines, grain and column descriptions, and every metric with its label,
  description, type, pipelines, time grain and the dimensions it can be grouped by.
- `data_agent/system_instruction.yaml`: the authored context of a BigQuery data agent, in the shape
  Google documents (a list of single-key maps: `system_instruction`, `tables` with fields and their
  aggregations from the measures, `relationships` from the entities, `glossaries` from the metrics,
  `additional_descriptions` from the derived and ratio metrics' formulas).
- `data_agent/example_queries.json`: one verified query per metric (`naturalLanguageQuestion`,
  `sqlQuery`), the metric by day as MetricFlow compiles it.

The third artefact, the warehouse comments, is built by dbt itself: `persist_docs` on gold and exposed,
and the `semantic.metrics` model (models/semantic/semantic_metrics.sql).

Table names are `database.schema.table` of the dbt target, so a BigQuery target yields
`project.dataset.table` and the compiled SQL its dialect, with no change here.
MetricFlow resolves dimensions and compiles SQL without a warehouse connection.

Usage, from dbt/ with the image's pins: python scripts/build_catalog.py [target_dir]
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

LAYER_TAGS = {"bronze", "silver", "gold", "exposed", "semantic"}

SYSTEM_INSTRUCTION = (
    "You answer questions about the lab's sales, partner returns and finance data. "
    "Compute a business figure only as its metric is defined in the glossary and the example queries; "
    "never invent another definition of revenue, orders or returns. Dates are UTC days."
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


class SemanticIndex:
    """Lookups over the semantic manifest and the dbt manifest that several artefacts share."""

    def __init__(self, manifest: dict, semantic_manifest: dict) -> None:
        self.semantic_models = {model["name"]: model for model in semantic_manifest["semantic_models"]}
        self.metrics = sorted(semantic_manifest["metrics"], key=lambda metric: metric["name"])
        self.model_of_measure = {
            measure["name"]: model for model in self.semantic_models.values() for measure in model["measures"]
        }
        self.tags_of_semantic_model = {}
        for node in manifest["semantic_models"].values():
            tags = [tag for node_id in node["depends_on"]["nodes"] for tag in manifest["nodes"][node_id]["tags"]]
            self.tags_of_semantic_model[node["name"]] = tags

    def models_of_metric(self, metric: dict) -> list[dict]:
        names = {self.model_of_measure[measure["name"]]["name"] for measure in metric["type_params"]["input_measures"]}
        return [self.semantic_models[name] for name in sorted(names)]

    def pipelines(self, metric: dict) -> list[str]:
        tags = {tag for model in self.models_of_metric(metric) for tag in self.tags_of_semantic_model[model["name"]]}
        return _pipelines(sorted(tags))

    def time_grain(self, metric: dict) -> str | None:
        grains = set()
        for model in self.models_of_metric(metric):
            time_dimension = model["defaults"]["agg_time_dimension"]
            for dimension in model["dimensions"]:
                if dimension["name"] == time_dimension:
                    grains.add(dimension["type_params"]["time_granularity"])
        return grains.pop() if len(grains) == 1 else None

    @staticmethod
    def table(model: dict) -> str:
        relation = model["node_relation"]
        return _relation(relation.get("database"), relation["schema_name"], relation["alias"])


def agent_catalog(manifest: dict, index: SemanticIndex, dimensions: Callable[[str], list[dict]]) -> dict:
    return {
        "models": public_models(manifest),
        "metrics": [
            {
                "name": metric["name"],
                "label": metric["label"],
                "description": metric["description"],
                "type": metric["type"],
                "pipelines": index.pipelines(metric),
                "time_grain": index.time_grain(metric),
                "semantic_models": [model["name"] for model in index.models_of_metric(metric)],
                "dimensions": dimensions(metric["name"]),
            }
            for metric in index.metrics
        ],
    }


def _item(**fields: object) -> list[dict]:
    """The documented authored-context form: every property is a single-key map in a list."""
    return [{key: value} for key, value in fields.items() if value not in (None, [], "")]


def system_instruction(index: SemanticIndex) -> list[dict]:
    tables = []
    for model in index.semantic_models.values():
        fields: dict[str, list[str]] = {}
        for measure in model["measures"]:
            aggregation = measure["agg"].replace("count_distinct", "count distinct")
            fields.setdefault(measure.get("expr") or measure["name"], []).append(aggregation)
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

    glossaries = [
        {"glossary": _item(term=metric["label"], description=metric["description"], synonyms=[metric["name"]])}
        for metric in index.metrics
    ]

    labels = {metric["name"]: metric["label"] for metric in index.metrics}
    descriptions = []
    for metric in index.metrics:
        params = metric["type_params"]
        if metric["type"] == "derived":
            formula = params["expr"]
            for name in sorted(labels, key=len, reverse=True):
                formula = formula.replace(name, labels[name])
            descriptions.append({"text": f"{metric['label']} = {formula}."})
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


def example_queries(index: SemanticIndex, compiled_sql: Callable[[str], str]) -> list[dict]:
    return [
        {
            "naturalLanguageQuestion": f"What is {metric['label'][0].lower() + metric['label'][1:]} by day?",
            "sqlQuery": compiled_sql(metric["name"]),
        }
        for metric in index.metrics
    ]


def _metricflow(project_dir: Path) -> tuple[Callable[[str], list[dict]], Callable[[str], str]]:
    """Dimensions and compiled SQL from MetricFlow's engine, set up as the mf CLI sets it up."""
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
            found.append({"name": name, "type": dimension.type.value, "description": description})
        return sorted(found, key=lambda dimension: dimension["name"])

    def compiled_sql(metric: str) -> str:
        request = MetricFlowQueryRequest.create(
            metric_names=[metric], group_by_names=["metric_time__day"], order_by_names=["metric_time__day"]
        )
        return engine.explain(request).sql_statement.sql

    return dimensions, compiled_sql


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "target")
    manifest = json.loads((target / "manifest.json").read_text())
    index = SemanticIndex(manifest, json.loads((target / "semantic_manifest.json").read_text()))
    dimensions, compiled_sql = _metricflow(target.resolve().parent)

    out = target / "catalog"
    (out / "data_agent").mkdir(parents=True, exist_ok=True)
    catalog = agent_catalog(manifest, index, dimensions)
    (out / "agent.json").write_text(json.dumps(catalog, indent=2) + "\n")
    (out / "data_agent" / "system_instruction.yaml").write_text(
        yaml.safe_dump(system_instruction(index), sort_keys=False, allow_unicode=True, width=110)
    )
    (out / "data_agent" / "example_queries.json").write_text(
        json.dumps(example_queries(index, compiled_sql), indent=2) + "\n"
    )
    print(f"build_catalog: {len(catalog['models'])} public models and {len(catalog['metrics'])} metrics in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
