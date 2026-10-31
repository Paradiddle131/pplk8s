"""The semantic layer as the agent sees it: S2's catalog, and MetricFlow's Python API to query it.

The catalog (`agent.json`, written by `make dbt-catalog`) holds the metrics' words and dimensions;
MetricFlow holds their definitions and compiles each request to SQL against the dbt project's
manifest. Nothing here accepts SQL: a request names metrics, dimensions and filter values, which are
checked against the catalog before MetricFlow builds the query (semantic/PLAN.md SL-2).

Env: `DBT_PROJECT_DIR` (the dbt project, parsed), `SEMANTIC_CATALOG` (default
`<DBT_PROJECT_DIR>/target/catalog/agent.json`), and dbt's own `DBT_*` connection variables, which
the lab points at the read-only `agent_metrics` role.
"""

from __future__ import annotations

import datetime
import decimal
import json
import os
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

MAX_ROWS = 200
OPERATORS = ("=", "!=", "in", "not in")


class QueryError(ValueError):
    """A request the semantic layer cannot answer; its message is safe to show the model."""


class Filter(BaseModel):
    """One condition on a categorical dimension, e.g. order__status = cancelled."""

    dimension: str
    operator: Literal["=", "!=", "in", "not in"] = "="
    values: list[str]


def project_dir() -> Path:
    if found := os.environ.get("DBT_PROJECT_DIR"):
        return Path(found)
    return Path(__file__).resolve().parents[4] / "dbt"  # the repo's dbt/, for a checkout


@dataclass(frozen=True)
class Catalog:
    metrics: dict[str, dict[str, Any]]
    models: list[dict[str, Any]] = field(default_factory=list)
    glossary: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> Catalog:
        path = path or Path(
            os.environ.get("SEMANTIC_CATALOG", project_dir() / "target" / "catalog" / "agent.json")
        )
        if not path.exists():
            raise FileNotFoundError(f"{path}: run `make dbt-catalog` first")
        data = json.loads(path.read_text())
        return cls(
            metrics={m["name"]: m for m in data["metrics"]},
            models=data["models"],
            glossary=data.get("glossary", []),
        )

    def metric(self, name: str) -> dict[str, Any]:
        if name not in self.metrics:
            raise QueryError(
                f"no metric named {name!r}; the metrics are {sorted(self.metrics)}. "
                "If none of them answers the question, "
                "say that the semantic layer has no such metric."
            )
        return self.metrics[name]

    def known_values(self, metric_names: list[str]) -> dict[str, list[str]]:
        """The values a categorical dimension's column declares (an accepted_values test), by name;
        a dimension that declares none is absent."""
        return {
            d["name"]: d["values"]
            for name in metric_names
            for d in self.metric(name)["dimensions"]
            if d.get("values")
        }

    def dimensions(self, metric_names: list[str]) -> dict[str, str]:
        """Dimensions every one of the metrics can be grouped or filtered by, with their type."""
        found = [
            {d["name"]: d["type"] for d in self.metric(name)["dimensions"]} for name in metric_names
        ]
        common = set.intersection(*(set(f) for f in found)) if found else set()
        return {name: found[0][name] for name in sorted(common)}


def _group_by_allowed(name: str, dimensions: dict[str, str]) -> bool:
    base, _, grain = name.rpartition("__")
    if name in dimensions:
        return True
    grains = ("day", "week", "month", "quarter", "year")
    return dimensions.get(base) == "time" and grain in grains


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def where_clause(
    item: Filter, dimensions: dict[str, str], known: dict[str, list[str]] | None = None
) -> str:
    """A MetricFlow where filter built from checked parts, never from the model's text.

    A value the dimension does not declare is refused with the values it does: a guessed value
    ("damaged goods" for "damaged") would match no row and come back as a confident zero.
    """
    categorical = sorted(name for name, kind in dimensions.items() if kind == "categorical")
    if item.dimension not in categorical:
        raise QueryError(
            f"cannot filter by {item.dimension!r}; filter on one of {categorical}, "
            "and limit time with start_date and end_date"
        )
    if not item.values:
        raise QueryError(f"filter on {item.dimension!r} has no values")
    values = (known or {}).get(item.dimension)
    if values is not None and (unknown := [v for v in item.values if v not in values]):
        raise QueryError(
            f"{item.dimension!r} has no value {', '.join(map(repr, unknown))}; "
            f"its values are {values}"
        )
    reference = "{{ Dimension('" + item.dimension + "') }}"
    if item.operator in ("=", "!="):
        if len(item.values) != 1:
            raise QueryError(f"operator {item.operator!r} takes exactly one value")
        operator = "=" if item.operator == "=" else "<>"
        return f"{reference} {operator} {_literal(item.values[0])}"
    values = ", ".join(_literal(v) for v in item.values)
    return f"{reference} {item.operator} ({values})"


def _date(value: str | None, name: str) -> datetime.datetime | None:
    if value is None:
        return None
    try:
        return datetime.datetime.combine(datetime.date.fromisoformat(value), datetime.time())
    except ValueError as e:
        raise QueryError(f"{name} must be a date like 2026-10-01, got {value!r}") from e


def _cell(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, datetime.datetime) and value.time() == datetime.time():
        return value.date().isoformat()
    if isinstance(value, datetime.date | datetime.datetime):
        return value.isoformat()
    return value


@dataclass
class MetricQuery:
    metrics: list[str]
    group_by: list[str] = field(default_factory=list)
    filters: list[Filter] = field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    order_by: list[str] = field(default_factory=list)
    limit: int | None = None

    def request(self, catalog: Catalog):  # -> MetricFlowQueryRequest
        from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

        if not self.metrics:
            raise QueryError("name at least one metric")
        dimensions = catalog.dimensions(self.metrics)
        for name in self.group_by:
            if not _group_by_allowed(name, dimensions):
                raise QueryError(
                    f"cannot group by {name!r}; the dimensions are {sorted(dimensions)}"
                )
        allowed_order = set(self.metrics) | set(self.group_by)
        for name in self.order_by:
            if name.removeprefix("-") not in allowed_order:
                raise QueryError(f"can only order by a requested metric or group-by, not {name!r}")
        limit = min(self.limit or MAX_ROWS, MAX_ROWS)
        known = catalog.known_values(self.metrics)
        return MetricFlowQueryRequest.create(
            metric_names=self.metrics,
            group_by_names=self.group_by or None,
            where_constraints=[where_clause(f, dimensions, known) for f in self.filters] or None,
            time_constraint_start=_date(self.start_date, "start_date"),
            time_constraint_end=_date(self.end_date, "end_date"),
            order_by_names=self.order_by or None,
            limit=limit,
        )


@cache
def engine():  # -> MetricFlowEngine
    """MetricFlow's engine on the dbt project, set up as the mf CLI sets it up (about 1 s)."""
    from dbt_metricflow.cli.cli_configuration import CLIConfiguration
    from metricflow.engine.metricflow_engine import MetricFlowEngine

    config = CLIConfiguration()
    config.setup(dbt_project_path=project_dir(), dbt_profiles_path=project_dir())
    return MetricFlowEngine(
        semantic_manifest_lookup=config.semantic_manifest_lookup, sql_client=config.sql_client
    )


def run(query: MetricQuery, catalog: Catalog) -> dict[str, Any]:
    """Rows and the compiled SQL of a metric query."""
    request = query.request(catalog)
    try:
        result = engine().query(request)
    except Exception as e:  # MetricFlow's own validation, e.g. an unknown time grain
        raise QueryError(f"the semantic layer rejected the query: {str(e).splitlines()[0]}") from e
    table = result.result_df
    columns = list(table.column_names) if table else []
    rows = [
        dict(zip(columns, map(_cell, row), strict=True)) for row in (table.rows if table else [])
    ]
    return {"columns": columns, "rows": rows, "row_count": len(rows), "sql": result.sql}
