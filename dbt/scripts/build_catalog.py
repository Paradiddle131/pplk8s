"""Write the agent catalog and the native data agent's authored context from the dbt manifests.

The semantic YAML and the model YAML are the single source of agent context (semantic/PLAN.md SL-3).
From `target/manifest.json` and `target/semantic_manifest.json` (after `dbt parse`) this writes, under
`target/catalog/`:

- `agent.json`: the catalog the metric toolset reads (S3): the public models (gold and exposed, SL-4)
  with their relation, pipelines, grain and column descriptions, and every metric with its label,
  description, type, pipelines, readiness products, time grain, the entities it can be grouped by (one row
  per customer, campaign, ...; their ids, no personal data) and the dimensions it can be grouped by,
  a categorical one with its known values when its column declares them (an `accepted_values` test), so the
  agent filters on a value the data holds instead of guessing one, and typed `numeric` when its column
  declares a numeric `data_type`, so the agent may compare it (MetricFlow knows only categorical and time).
  A metric's readiness products are the `ops.readiness` products of the models it reads,
  `<pipeline>.<layer>` (e.g. `sales.silver`), which is how the agent states its freshness (SL-4).
  The metrics defined for another warehouse only (`unavailable_metrics`: a BigQuery-only median on Postgres),
  with their dialects, so the agent declines them by name instead of guessing.
  The time spine's custom grains (`custom_grains`: the fiscal quarter and year) with their descriptions.
  And the glossary: the business terms that are not metrics, from `config.meta.glossary` on the models
  that hold them, each with the metrics and dimensions it maps to; and the saved queries (#164), each with
  its question (`config.meta.question`), metrics, group-bys, filters and readiness products.
  And each semantic model's table with its readiness products, so an answer that names tables instead of
  metrics (a native data agent's generated SQL) still finds its freshness (#207); and each governed table
  (governed.py, SL-24) with its metrics and their readiness products, for the same reason.
- `data_agent/context.json`: a BigQuery data agent's whole context in the Conversational Analytics API's v1
  structured form (`Context`, ready for a DataAgent's `dataAnalyticsAgent.publishedContext`; #204), which
  Google prefers wherever a structured field exists: `datasourceReferences.bq.tableReferences`, one per table
  the semantic models and the time spine read, each with its description, synonyms (the semantic model's and
  its primary entity's names), tags (its layer and pipelines) and fields (each declared column but a
  personal one, with its description, the entities and dimensions it backs as synonyms and its role as
  tags); `glossaryTerms`, one per metric (its label, description and name) and one per glossary term (whose
  description names its metrics and dimensions, as the term has no field for them); `exampleQueries`; and
  `systemInstruction`, the YAML below as text.
- `data_agent/system_instruction.yaml`: what the structured form lacks, in the authored-context shape Google
  documents (a list of single-key maps: `system_instruction`, `tables` with fields and their aggregations from
  the simple metrics, `relationships` from the entities, `additional_descriptions` from the derived, ratio and
  cumulative metrics' formulas).
- `data_agent/example_queries.json`: the verified queries (`naturalLanguageQuestion`, `sqlQuery`): one per
  metric, the metric by day, and one per saved query, its question, each as MetricFlow compiles it; the same
  list as context.json's `exampleQueries`.
- `data_agent_governed/context.json`: a second data agent's v1 `Context` (SL-24, `pplk8s-governed`), whose only
  tables are the governed tables the BigQuery target builds (dbt/models/governed/, from MetricFlow's compiled
  SQL) and the time spine: the governed tables' words (governed.py), a system instruction saying the numbers
  are computed already and how a non-additive one combines, each metric's glossary term naming its governed
  column, each glossary term the governed columns of its metrics and dimensions, and verified queries that
  only select and sum governed columns (each metric by day, each ratio over a week from its components).

The third artefact, the warehouse comments, is built by dbt itself: `persist_docs` on gold and exposed,
and the `semantic.metrics` and `semantic.glossary` models (models/semantic/).

Table names are `database.schema.table` of the dbt target, so a BigQuery target yields
`project.dataset.table` and the compiled SQL its dialect, with no change here.
MetricFlow resolves dimensions and compiles SQL without a warehouse connection.

Usage, from dbt/ with the image's pins: python scripts/build_catalog.py [target_dir]
"""

from __future__ import annotations

import functools
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import yaml
from governed import (
    DATASET,
    TIME,
    TOTAL,
    Table,
    column_descriptions,
    plan,
    ratio_components,
    table_description,
    table_of,
)

LAYER_TAGS = {"bronze", "silver", "gold", "exposed", "semantic"}

SYSTEM_INSTRUCTION = (
    "You answer business questions about the data these tables describe. "
    "Compute a business figure only as its metric is defined in the glossary and the example queries; "
    "never invent another definition of a figure a metric defines. Dates are UTC days. "
    "A glossary term that is not a metric names the metrics and dimensions it maps to."
)

# Knowledge Catalog: "the data agent can import a maximum of 10 glossary terms per table" and ignores the rest
# (docs.cloud.google.com/knowledge-catalog/docs/manage-glossaries); check_catalog.py holds glossary_tables to it.
GLOSSARY_TERMS_PER_TABLE = 10


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


def custom_grains(manifest: dict, index: SemanticIndex) -> list[dict]:
    """The time spine's custom granularities (the fiscal quarter and year), each with its column's description,
    so a time dimension groups by `__fiscal_quarter` as by `__month`."""
    found = []
    for spine in index.time_spines:
        model = next(
            (
                n
                for n in manifest["nodes"].values()
                if n["resource_type"] == "model" and n.get("alias") == spine["node_relation"]["alias"]
            ),
            {},
        )
        for grain in spine.get("custom_granularities", []):
            column = grain.get("column_name") or grain["name"]
            description = ((model.get("columns") or {}).get(column) or {}).get("description") or ""
            found.append({"name": grain["name"], "description": " ".join(description.split())})
    return sorted(found, key=lambda grain: grain["name"])


def unavailable_metrics(manifest: dict) -> list[dict]:
    """The metrics defined for another warehouse only (`config.meta.dialects`, disabled on this target by
    `enabled: "{{ target.type == ... }}"`), so the agent can say a metric exists, but not here (SL-6)."""
    found = []
    for nodes in manifest.get("disabled", {}).values():
        for node in nodes:
            dialects = ((node.get("config") or {}).get("meta") or {}).get("dialects")
            if node.get("resource_type") == "metric" and dialects:
                found.append(
                    {
                        "name": node["name"],
                        "label": node.get("label") or "",
                        "description": node.get("description") or "",
                        "dialects": list(dialects),
                    }
                )
    return sorted(found, key=lambda metric: metric["name"])


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
        self.time_spines = semantic_manifest.get("project_configuration", {}).get("time_spines", [])
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
        return sorted({p for model in self.models_of_metric(metric) for p in self.readiness_of_model(model)})

    def readiness_of_model(self, model: dict) -> list[str]:
        """The readiness products one semantic model's table is: `<pipeline>.<layer>` from its dbt tags."""
        tags = self.tags_of_semantic_model[model["name"]]
        layers = [tag for tag in tags if tag in LAYER_TAGS]
        return sorted({f"{pipeline}.{layer}" for pipeline in _pipelines(tags) for layer in layers})

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

    @property
    def database(self) -> str | None:
        """The target's database (on BigQuery, its project) the semantic models' tables are in."""
        return next(iter(self.semantic_models.values()))["node_relation"].get("database")

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


def governed_tables(index: SemanticIndex, tables: list[Table]) -> list[dict]:
    """The governed tables with their relation, kind, metrics and the readiness products of those metrics."""
    metrics = {metric["name"]: metric for metric in index.metrics}
    return [
        {
            "name": table.name,
            "relation": _relation(index.database, DATASET, table.name),
            "kind": table.kind,
            "metrics": list(table.metrics),
            "readiness": sorted({p for name in table.metrics for p in index.readiness(metrics[name])}),
        }
        for table in tables
    ]


def agent_catalog(
    manifest: dict,
    index: SemanticIndex,
    dimensions: Callable[[str], list[dict]],
    entities: Callable[[str], list[dict]] = lambda metric: [],
) -> dict:
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
                "entities": entities(metric["name"]),
            }
            for metric in index.metrics
        ],
        # The table each semantic model reads, and its readiness products: how an answer that names its
        # tables, not its metrics (a data agent's generated SQL), finds its freshness (#207).
        "semantic_models": [
            {"name": model["name"], "relation": index.table(model), "readiness": index.readiness_of_model(model)}
            for model in sorted(index.semantic_models.values(), key=lambda model: model["name"])
        ],
        "saved_queries": saved_queries(index),
        # The governed tables the BigQuery target builds (governed.py, SL-24), each with its metrics' readiness
        # products: a governed data agent's SQL names these, not the semantic models' tables.
        "governed_tables": governed_tables(index, plan(index.metrics, dimensions)),
        "unavailable_metrics": unavailable_metrics(manifest),
        "custom_grains": custom_grains(manifest, index),
    }


def _item(**fields: object) -> list[dict]:
    """The documented authored-context form: every property is a single-key map in a list."""
    return [{key: value} for key, value in fields.items() if value not in (None, [], "")]


def _primary_key(model: dict) -> str:
    entity = next(entity for entity in model["entities"] if entity["type"] == "primary")
    return entity.get("expr") or entity["name"]


def _aggregations(index: SemanticIndex) -> dict[str, dict[str, list[str]]]:
    """The aggregations the simple metrics apply, by semantic model and column."""
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
    return aggregations


def system_instruction(index: SemanticIndex) -> list[dict]:
    """What the v1 structured context has no field for: the instruction, the aggregations, the relationships
    (v1's `schemaRelationships` are derived ones, from Dataplex) and the formulas."""
    aggregations = _aggregations(index)
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
        additional_descriptions=descriptions,
    )


def _fields(**fields: object) -> dict:
    """A v1 message: the fields that hold something."""
    return {key: value for key, value in fields.items() if value not in (None, [], "")}


def _words(text: str | None) -> str:
    return " ".join((text or "").split())


def glossary_terms(index: SemanticIndex, terms: list[dict]) -> list[dict]:
    """The v1 `glossaryTerms`: each metric (its label, description and name), then each glossary term."""
    labels = {metric["name"]: metric["label"] for metric in index.metrics}
    found = [
        _fields(displayName=metric["label"], description=_words(metric["description"]), labels=[metric["name"]])
        for metric in index.metrics
    ]
    for term in terms:
        # A glossary term has no field for a mapping, so the term's description names it.
        mapping = []
        if term["metrics"]:
            mapping.append(f"Metrics: {', '.join(labels.get(name, name) for name in term['metrics'])}.")
        if term["dimensions"]:
            mapping.append(f"Dimensions: {', '.join(term['dimensions'])}.")
        description = " ".join([term["description"], *mapping])
        found.append(_fields(displayName=term["term"], description=description, labels=term["synonyms"]))
    return found


def glossary_tables(manifest: dict, index: SemanticIndex, terms: list[dict]) -> dict[str, list[str]]:
    """The glossary terms each table would carry in Knowledge Catalog, by display name: a simple metric's on the
    table it aggregates, a glossary term's on the model that defines it (`config.meta.glossary`); a ratio,
    derived, cumulative or conversion metric combines other metrics, so it sits on no table of its own."""
    relations = {
        node["name"]: _relation(node.get("database"), node["schema"], node["alias"])
        for node in manifest["nodes"].values()
        if node["resource_type"] == "model"
    }
    found: dict[str, list[str]] = {}
    for metric in index.metrics:
        params = metric["type_params"]["metric_aggregation_params"]
        if params is not None:
            table = index.table(index.semantic_models[params["semantic_model"]])
            found.setdefault(table, []).append(metric["label"])
    for term in terms:
        found.setdefault(relations[term["model"]], []).append(term["term"])
    return dict(sorted(found.items()))


def table_references(manifest: dict, index: SemanticIndex) -> list[dict]:
    """The v1 `datasourceReferences.bq.tableReferences`: every table a semantic model or the time spine reads,
    with the dbt model's words; a personal column (`meta: {pii: true}`) is left out, as no agent reads it."""
    models = {
        (node.get("database"), node["schema"], node["alias"]): node
        for node in manifest["nodes"].values()
        if node["resource_type"] == "model"
    }
    aggregations = _aggregations(index)
    tables = []
    for model in index.semantic_models.values():
        relation = model["node_relation"]
        primary = next((entity["name"] for entity in model["entities"] if entity["type"] == "primary"), None)
        synonyms: dict[str, list[str]] = {}
        tags: dict[str, list[str]] = {}
        for entity in model["entities"]:
            column = entity.get("expr") or entity["name"]
            synonyms.setdefault(column, []).append(entity["name"])
            tags.setdefault(column, []).append(f"{entity['type']} key")
        for dimension in model["dimensions"]:
            column = dimension.get("expr") or dimension["name"]
            synonyms.setdefault(column, []).append(dimension["name"])
            kind = "numeric" if index.is_numeric(model["name"], column) else dimension["type"]
            tags.setdefault(column, []).append(f"{kind} dimension")
        for column in aggregations[model["name"]]:
            tags.setdefault(column, []).append("measure")
        tables.append((relation, {model["name"], primary} - {relation["alias"], None}, synonyms, tags))
    for spine in index.time_spines:
        tables.append((spine["node_relation"], set(), {}, {spine["primary_column"]["name"]: ["time spine"]}))

    found = []
    for relation, table_synonyms, synonyms, tags in sorted(tables, key=lambda t: (t[0]["schema_name"], t[0]["alias"])):
        node = models[(relation.get("database"), relation["schema_name"], relation["alias"])]
        fields = [
            _fields(
                name=name,
                type=(column.get("data_type") or "").upper(),
                description=_words(column.get("description")),
                synonyms=sorted(set(synonyms.get(name, [])) - {name}),
                tags=sorted(set(tags.get(name, []))),
            )
            for name, column in node["columns"].items()
            if not ((column.get("config") or {}).get("meta", {}).get("pii") or (column.get("meta") or {}).get("pii"))
        ]
        found.append(
            _fields(
                projectId=relation.get("database"),
                datasetId=relation["schema_name"],
                tableId=relation["alias"],
                schema=_fields(
                    description=_words(node["description"]),
                    synonyms=sorted(table_synonyms),
                    tags=sorted(node["tags"]),
                    fields=fields,
                ),
            )
        )
    return found


def context(manifest: dict, index: SemanticIndex, terms: list[dict], instruction: str, queries: list[dict]) -> dict:
    """The data agent's v1 `Context`: the structured fields, and the authored-context YAML for the rest."""
    return _fields(
        datasourceReferences={"bq": {"tableReferences": table_references(manifest, index)}},
        systemInstruction=instruction,
        glossaryTerms=glossary_terms(index, terms),
        exampleQueries=queries,
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


GOVERNED_INSTRUCTION = (
    "You answer business questions from governed tables: every number in them was computed by MetricFlow from "
    "the business's metric definitions, so select, filter and add up those numbers, and never re-derive a metric "
    "from other data or invent another definition. "
    f"A table named *_daily holds additive metrics, one row per day ({TIME}) and combination of its dimensions: "
    "filter the days and dimension values asked and SUM the metric's column. "
    "A table named *_by_period holds metrics that do not add up (ratios, distinct counts, averages, balances, "
    "running totals, conversion rates, growth): read the one row of the grain asked (day, week from Monday, or "
    f"calendar month, by period_start) and slice ('{TOTAL}', or on a day one dimension and its value), and never "
    "SUM or AVG such a column over rows. "
    "For a span that is not one such row, each column's description says how to combine the daily tables' "
    "additive columns (a ratio is the SUM of its numerator divided by the SUM of its denominator over the same "
    "rows); where it says there is no additive form, say that the governed tables cannot answer for that span. "
    "Fiscal quarters and years: join the time spine on its date_day to the day. Dates are UTC days. "
    "A glossary term names the governed columns its metrics and dimensions are."
)
# The span the ratios' verified queries combine their components over: one ISO week outside the eval's dates.
EXAMPLE_SPAN = ("2026-09-07", "2026-09-13", "the week of 7 September 2026")


def governed_context(
    manifest: dict, index: SemanticIndex, tables: list[Table], terms: list[dict], dimensions: Callable
) -> dict:
    """The governed data agent's v1 `Context` (SL-24): the governed tables and the time spine as its only tables,
    each metric's glossary term naming its governed column, verified queries that only select and sum them."""
    metrics = {metric["name"]: metric for metric in index.metrics}

    def described(name: str) -> dict[str, str]:
        return {d["name"]: d.get("description") or "" for d in dimensions(name)}

    refs = []
    for table in tables:
        dims = {key: text for name in table.metrics for key, text in described(name).items()}
        fields = []
        for column, text in column_descriptions(table, metrics, tables, dims).items():
            if column in table.metrics:
                kind = ["additive measure"] if table.kind == "daily" else ["non-additive measure"]
                synonyms = [metrics[column]["label"]]
            elif column in (TIME, "period_start"):
                kind, synonyms = ["time dimension"], []
            else:
                kind, synonyms = ["categorical dimension"], []
            types = {TIME: "DATE", "period_start": "DATE", "grain": "STRING", "slice": "STRING"}
            fields.append(
                _fields(name=column, type=types.get(column, ""), description=text, synonyms=synonyms, tags=kind)
            )
        refs.append(
            _fields(
                projectId=index.database,
                datasetId=DATASET,
                tableId=table.name,
                schema=_fields(
                    description=table_description(table), tags=["governed", table.kind, table.home], fields=fields
                ),
            )
        )
    spines = {spine["node_relation"]["alias"] for spine in index.time_spines}
    refs += [ref for ref in table_references(manifest, index) if ref["tableId"] in spines]

    def column_of(name: str) -> str:
        table = table_of(tables, name)
        how = "add it up over rows" if table.kind == "daily" else "one row per period and slice, never added up"
        return f"{DATASET}.{table.name}.{name} ({how})"

    glossary = [
        _fields(
            displayName=metric["label"],
            description=f"{_words(metric['description'])} Governed column: {column_of(metric['name'])}.",
            labels=[metric["name"]],
        )
        for metric in index.metrics
    ]
    for term in terms:
        mapping = []
        if term["metrics"]:
            mapping.append(f"Metrics: {', '.join(column_of(name) for name in term['metrics'] if name in metrics)}.")
        for dimension in term["dimensions"]:
            daily = [f"{DATASET}.{t.name}" for t in tables if t.kind == "daily" and dimension in t.dimensions]
            sliced = [f"{DATASET}.{t.name}" for t in tables if t.kind == "by_period" and dimension in t.dimensions]
            where = [f"a column of {', '.join(daily)}"] if daily else []
            where += [f"slice '{dimension}' of {', '.join(sliced)}"] if sliced else []
            mapping.append(f"Dimension {dimension}: {'; '.join(where) or 'in no governed table'}.")
        glossary.append(
            _fields(
                displayName=term["term"], description=" ".join([term["description"], *mapping]), labels=term["synonyms"]
            )
        )

    def ref(table: Table) -> str:
        return ".".join(f"`{part}`" for part in (index.database, DATASET, table.name) if part)

    queries = []
    for metric in index.metrics:
        table = table_of(tables, metric["name"])
        name = metric["name"]
        if table.kind == "daily":
            sql = f"SELECT {TIME}, SUM({name}) AS {name}\nFROM {ref(table)}\nGROUP BY {TIME}\nORDER BY {TIME}"
        else:
            sql = (
                f"SELECT period_start AS {TIME}, {name}\nFROM {ref(table)}\n"
                f"WHERE grain = 'day' AND slice = '{TOTAL}'\nORDER BY period_start"
            )
        label = metric["label"][0].lower() + metric["label"][1:]
        queries.append({"naturalLanguageQuestion": f"What is {label} by day?", "sqlQuery": sql})
    start, end, words = EXAMPLE_SPAN
    for metric in index.metrics:
        found = ratio_components(metric, metrics, tables)
        if not found:
            continue
        sums = []
        for part in found:
            where = f"{TIME} BETWEEN DATE '{start}' AND DATE '{end}'" + (
                f" AND {part.condition}" if part.condition else ""
            )
            sums.append(f"(SELECT SUM({part.column}) FROM {ref(part.table)} WHERE {where})")
        label = metric["label"][0].lower() + metric["label"][1:]
        queries.append(
            {
                "naturalLanguageQuestion": f"What was {label} over {words}?",
                "sqlQuery": f"SELECT {sums[0]}\n  / NULLIF({sums[1]}, 0) AS {metric['name']}",
            }
        )
    return _fields(
        datasourceReferences={"bq": {"tableReferences": refs}},
        systemInstruction=GOVERNED_INSTRUCTION,
        glossaryTerms=glossary,
        exampleQueries=queries,
    )


class MetricFlow(NamedTuple):
    """What the generators ask MetricFlow's engine, offline."""

    dimensions: Callable[[str], list[dict]]
    entities: Callable[[str], list[dict]]
    compiled_sql: Callable[[str], str]
    compiled_saved_query: Callable[[str], str]
    compiled: Callable[[list[str], list[str]], str]


def _metricflow(project_dir: Path, index: SemanticIndex) -> MetricFlow:
    """Dimensions and compiled SQL, of a metric, of a saved query and of metrics by group-bys, from MetricFlow's
    engine, set up as the mf CLI sets it up."""
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

    def entities(metric: str) -> list[dict]:
        """The entities a metric can be grouped by (one row per customer, campaign, ...), as their ids."""
        # One entry per name: an entity reached through two models (campaign on spend and on leads) is one
        # group-by; its description is the first in order, so the catalog is the same on every run.
        found: dict[str, str] = {}
        for entity in sorted(engine.entities_for_metrics([metric]), key=lambda e: (e.name, e.description or "")):
            found.setdefault(entity.name, entity.description or "")
        return [{"name": name, "description": description} for name, description in sorted(found.items())]

    def compiled_sql(metric: str) -> str:
        request = MetricFlowQueryRequest.create(
            metric_names=[metric], group_by_names=["metric_time__day"], order_by_names=["metric_time__day"]
        )
        return engine.explain(request).sql_statement.sql

    def compiled_saved_query(name: str) -> str:
        return engine.explain(MetricFlowQueryRequest.create(saved_query_name=name)).sql_statement.sql

    def compiled(metrics: list[str], group_by: list[str]) -> str:
        request = MetricFlowQueryRequest.create(metric_names=metrics, group_by_names=group_by)
        return engine.explain(request).sql_statement.sql

    return MetricFlow(dimensions, entities, compiled_sql, compiled_saved_query, compiled)


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "target")
    manifest = json.loads((target / "manifest.json").read_text())
    index = SemanticIndex(manifest, json.loads((target / "semantic_manifest.json").read_text()))
    dimensions, entities, compiled_sql, compiled_saved_query, _ = _metricflow(
        Path(__file__).resolve().parents[1], index
    )
    dimensions = functools.cache(dimensions)

    out = target / "catalog"
    (out / "data_agent").mkdir(parents=True, exist_ok=True)
    (out / "data_agent_governed").mkdir(parents=True, exist_ok=True)
    catalog = agent_catalog(manifest, index, dimensions, entities)
    (out / "agent.json").write_text(json.dumps(catalog, indent=2) + "\n")
    instruction = yaml.safe_dump(system_instruction(index), sort_keys=False, allow_unicode=True, width=110)
    (out / "data_agent" / "system_instruction.yaml").write_text(instruction)
    queries = example_queries(index, compiled_sql, compiled_saved_query)
    (out / "data_agent" / "example_queries.json").write_text(json.dumps(queries, indent=2) + "\n")
    data_agent = context(manifest, index, catalog["glossary"], instruction, queries)
    (out / "data_agent" / "context.json").write_text(json.dumps(data_agent, indent=2) + "\n")
    tables = plan(index.metrics, dimensions)
    governed = governed_context(manifest, index, tables, catalog["glossary"], dimensions)
    (out / "data_agent_governed" / "context.json").write_text(json.dumps(governed, indent=2) + "\n")
    print(
        f"build_catalog: {len(catalog['models'])} public models, {len(catalog['metrics'])} metrics "
        f"and {len(catalog['glossary'])} glossary terms in {out}; {len(catalog['saved_queries'])} saved queries; "
        f"context.json: {len(data_agent['datasourceReferences']['bq']['tableReferences'])} tables, "
        f"{len(data_agent['glossaryTerms'])} glossary terms and {len(data_agent['exampleQueries'])} example queries; "
        f"the governed context: {len(governed['datasourceReferences']['bq']['tableReferences'])} tables and "
        f"{len(governed['exampleQueries'])} example queries"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
