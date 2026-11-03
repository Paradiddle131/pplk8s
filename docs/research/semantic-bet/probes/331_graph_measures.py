"""Which of the project's MetricFlow metrics compile to BigQuery graph measures, and the graph that holds them.

Measures: for each metric in a manifest parsed on a BigQuery target, whether it fits a graph measure under the
documented rules (one element table; SUM, AVG, COUNT, MIN, MAX, DISTINCT allowed, CASE inside an aggregate;
derived measures through AGG() on the same element table; no windows, offsets or percentiles), with the reason
when not; then a CREATE PROPERTY GRAPH statement: one node table per semantic model keyed by its primary entity,
carrying its dimensions and its compiling metrics as measures, and one edge per foreign entity whose primary
model is a node. The translation is this probe's, not MetricFlow's: a metric's filters become a CASE inside its
aggregate, and only filters on the metric's own model's dimensions translate.
Run (from the repo root): python3 -I docs/research/semantic-bet/probes/331_graph_measures.py <manifest.json> [out.sql]
<manifest.json> is target/manifest.json of a copy of dbt/ parsed on the `bigquery` target (as
tests/e2e/governed-models.sh makes one). Offline: reads one file, writes one file (default bet_graph.sql).
"""

import json
import re
import sys
from pathlib import Path

AGGS = {
    "sum": "SUM({})",
    "count": "COUNT({})",
    "count_distinct": "COUNT(DISTINCT {})",
    "average": "AVG({})",
}
AGGS |= {"min": "MIN({})", "max": "MAX({})", "sum_boolean": "SUM(CAST({} AS INT64))"}
DIMENSION = re.compile(r"\{\{\s*Dimension\('(\w+)__(\w+)'\)\s*\}\}")


def main() -> int:
    manifest = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "bet_graph.sql")
    models = {sm["name"]: sm for sm in manifest["semantic_models"].values()}
    metrics = {m["name"]: m for m in manifest["metrics"].values()}
    measures: dict[
        str, tuple[str, str]
    ] = {}  # metric -> (semantic model, measure expression)
    reasons: dict[str, str] = {}

    def own_dimension(model: dict, entity: str, name: str) -> str | None:
        entities = {e["name"] for e in model["entities"]}
        for dim in model["dimensions"]:
            if entity in entities and dim["name"] == name:
                return dim.get("expr") or dim["name"]
        return None

    def where(model: dict, metric: dict) -> tuple[str | None, str | None]:
        """The metric's filters as one SQL condition on its own model's columns, or the reason they don't fit."""
        conditions = []
        for f in (metric.get("filter") or {}).get("where_filters", []):
            template = f["where_sql_template"]
            rest = DIMENSION.sub("", template)
            if "{{" in rest:
                return None, f"filter uses more than Dimension(): {template}"
            for entity, name in DIMENSION.findall(template):
                if own_dimension(model, entity, name) is None:
                    return (
                        None,
                        f"filter on another table's dimension: {entity}__{name}",
                    )
            conditions.append(
                DIMENSION.sub(lambda m: own_dimension(model, m[1], m[2]), template)
            )
        return (" AND ".join(f"({c})" for c in conditions) or None), None

    def classify(name: str) -> None:
        if name in measures or name in reasons:
            return
        metric = metrics[name]
        params = metric["type_params"]
        kind = metric["type"]
        if kind in ("cumulative", "conversion"):
            reasons[name] = (
                f"{kind}: needs a window or a funnel, which a measure has no form for"
            )
        elif kind == "simple":
            agg = params["metric_aggregation_params"]
            model = models[agg["semantic_model"]]
            if agg["non_additive_dimension"]:
                reasons[name] = (
                    "semi-additive (non_additive_dimension): needs the last value per period"
                )
            elif agg["agg"] not in AGGS:
                reasons[name] = (
                    f"aggregation {agg['agg']} is not one a measure supports"
                )
            else:
                condition, why = where(model, metric)
                expr = params["expr"] or name
                if why:
                    reasons[name] = why
                else:
                    value = (
                        f"CASE WHEN {condition} THEN {expr} END" if condition else expr
                    )
                    measures[name] = (model["name"], AGGS[agg["agg"]].format(value))
        else:  # ratio, derived
            inputs = (
                [params["numerator"], params["denominator"]]
                if kind == "ratio"
                else params["metrics"]
            )
            if any(i.get("offset_window") or i.get("offset_to_grain") for i in inputs):
                reasons[name] = (
                    "an input is offset in time (offset_window or offset_to_grain)"
                )
                return
            if metric.get("filter") or any(i.get("filter") for i in inputs):
                reasons[name] = f"a filter on the {kind} metric or its inputs"
                return
            for i in inputs:
                classify(i["name"])
            missing = [i["name"] for i in inputs if i["name"] not in measures]
            homes = {measures[i["name"]][0] for i in inputs if i["name"] in measures}
            if missing:
                reasons[name] = f"input {', '.join(missing)} does not compile"
            elif len(homes) > 1:
                reasons[name] = (
                    f"inputs on different tables ({', '.join(sorted(homes))})"
                )
            elif kind == "ratio":
                num, den = (f"AGG({i['name']})" for i in inputs)
                measures[name] = (homes.pop(), f"SAFE_DIVIDE({num}, NULLIF({den}, 0))")
            else:
                expr = params["expr"]
                for i in inputs:
                    expr = re.sub(
                        rf"\b{i.get('alias') or i['name']}\b", f"AGG({i['name']})", expr
                    )
                measures[name] = (homes.pop(), expr)

    for name in sorted(metrics):
        classify(name)

    nodes, edges = [], []
    for model in sorted(models.values(), key=lambda m: m["name"]):
        rel = model["node_relation"]
        table = f"{rel['schema_name']}.{rel['alias']}"
        primary = [e for e in model["entities"] if e["type"] == "primary"]
        if not primary:
            for name, (home, _) in list(measures.items()):
                if home == model["name"]:
                    reasons[name] = (
                        "its semantic model has no primary entity to key a node table"
                    )
                    del measures[name]
            continue
        key = primary[0].get("expr") or primary[0]["name"]
        props = sorted(
            {
                d.get("expr") or d["name"]
                for d in model["dimensions"]
                if (d.get("expr") or d["name"]).isidentifier()
            }
        )
        mine = [
            f"MEASURE({expr}) AS {n}"
            for n, (home, expr) in sorted(measures.items())
            if home == model["name"]
        ]
        nodes.append(
            f"    {table} AS {model['name']}\n      KEY ({key})\n      PROPERTIES ({', '.join([key, *props, *mine])})"
        )
    keyed = {
        e["name"]: (sm["name"], e.get("expr") or e["name"])
        for sm in models.values()
        for e in sm["entities"]
        if e["type"] == "primary"
    }
    for model in sorted(models.values(), key=lambda m: m["name"]):
        primary = [e for e in model["entities"] if e["type"] == "primary"]
        rel = model["node_relation"]
        for e in model["entities"]:
            if (
                e["type"] == "foreign"
                and primary
                and e["name"] in keyed
                and keyed[e["name"]][0] != model["name"]
            ):
                target, target_key = keyed[e["name"]]
                source_key = primary[0].get("expr") or primary[0]["name"]
                edges.append(
                    f"    {rel['schema_name']}.{rel['alias']} AS {model['name']}_to_{target}\n"
                    f"      KEY ({source_key})\n"
                    f"      SOURCE KEY ({source_key}) REFERENCES {model['name']} ({source_key})\n"
                    f"      DESTINATION KEY ({e.get('expr') or e['name']}) REFERENCES {target} ({target_key})"
                )
    statement = "CREATE OR REPLACE PROPERTY GRAPH bet_graph.metrics\n  NODE TABLES (\n"
    statement += ",\n".join(nodes) + "\n  )"
    if edges:
        statement += "\n  EDGE TABLES (\n" + ",\n".join(edges) + "\n  )"
    out.write_text(
        "-- Written by probes/331_graph_measures.py from the project's manifest; not run yet.\n"
        "CREATE SCHEMA IF NOT EXISTS bet_graph OPTIONS (location = 'US');\n\n"
        + statement
        + ";\n"
    )

    by_kind: dict[str, list[int]] = {}
    for name, metric in metrics.items():
        by_kind.setdefault(metric["type"], [0, 0])[name in measures] += 1
    print(
        f"{len(measures)} of {len(metrics)} metrics compile to graph measures; {len(nodes)} node and {len(edges)} edge tables"
    )
    for kind, (no, yes) in sorted(by_kind.items()):
        print(f"  {kind}: {yes} of {yes + no}")
    for name in sorted(reasons):
        print(f"  no  {name} ({metrics[name]['type']}): {reasons[name]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
