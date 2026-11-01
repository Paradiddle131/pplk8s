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
OPERATORS = ("=", "!=", "in", "not in", ">", ">=", "<", "<=", "between")
# The operators each dimension type takes: a categorical value matched, a date or number compared.
OPERATORS_BY_TYPE = {
    "categorical": ("=", "!=", "in", "not in"),
    "time": ("=", "!=", ">", ">=", "<", "<=", "between"),
    "numeric": OPERATORS,
}
# MetricFlow renders a where filter as a Jinja template before it becomes SQL, so a value holding a
# delimiter would be evaluated ('{{ 7*7 }}' filters on '49'), not compared as the text sent.
JINJA_DELIMITERS = ("{{", "{%", "{#")


class QueryError(ValueError):
    """A request the semantic layer cannot answer; its message is safe to show the model."""


class Filter(BaseModel):
    """One condition on a dimension, e.g. order__status = cancelled, customer__signup_date >=
    2024-09-01 or order__amount between 10 and 50."""

    dimension: str
    operator: Literal["=", "!=", "in", "not in", ">", ">=", "<", "<=", "between"] = "="
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
    saved_queries: dict[str, dict[str, Any]] = field(default_factory=dict)

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
            saved_queries={q["name"]: q for q in data.get("saved_queries", [])},
        )

    def metric(self, name: str) -> dict[str, Any]:
        if name not in self.metrics:
            raise QueryError(
                f"no metric named {name!r}; the metrics are {sorted(self.metrics)}. "
                "If none of them answers the question, "
                "say that the semantic layer has no such metric."
            )
        return self.metrics[name]

    def saved_query(self, name: str) -> dict[str, Any]:
        if name not in self.saved_queries:
            raise QueryError(
                f"no saved query named {name!r}; the saved queries are {sorted(self.saved_queries)}"
            )
        return self.saved_queries[name]

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


def _iso_date(value: str, dimension: str) -> str:
    """A date at the day grain every time dimension has, written back from its parsed form."""
    try:
        if len(value) != 10:
            raise ValueError(value)
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError as e:
        raise QueryError(
            f"{dimension!r} is a time dimension: each value must be a date like 2024-09-01, "
            f"got {value!r}"
        ) from e


def _number(value: str, dimension: str) -> decimal.Decimal:
    """A plain decimal number (no exponent, no NaN or infinity), so its text is all digits."""
    try:
        number = decimal.Decimal(value.strip())
        if not number.is_finite() or "e" in value.lower():
            raise decimal.InvalidOperation(value)
    except decimal.InvalidOperation as e:
        raise QueryError(
            f"{dimension!r} is numeric: each value must be a number like 100 or 99.50, "
            f"got {value!r}"
        ) from e
    return number


def where_clause(
    item: Filter, dimensions: dict[str, str], known: dict[str, list[str]] | None = None
) -> str:
    """A MetricFlow where filter built from checked parts, never from the model's text.

    A categorical value the dimension does not declare is refused with the values it does: a
    guessed value ("damaged goods" for "damaged") would match no row and come back as a confident
    zero. A time dimension takes ISO dates and a numeric one numbers, each parsed and written back,
    so no text the model sent reaches the filter. A value holding a Jinja delimiter is refused for
    every type: MetricFlow would render it, and filter on the result.
    """
    if item.dimension == "metric_time" or item.dimension.startswith("metric_time__"):
        raise QueryError("limit metric_time with start_date and end_date, not a filter")
    kind = dimensions.get(item.dimension)
    if kind is None:
        raise QueryError(
            f"cannot filter by {item.dimension!r}; filter on one of {sorted(dimensions)}, "
            "and limit time with start_date and end_date"
        )
    if not item.values:
        raise QueryError(f"filter on {item.dimension!r} has no values")
    if templated := [v for v in item.values if any(d in v for d in JINJA_DELIMITERS)]:
        raise QueryError(
            f"filter value {', '.join(map(repr, templated))} on {item.dimension!r} holds a "
            f"template delimiter ({', '.join(JINJA_DELIMITERS)}); send the value as plain text"
        )
    allowed = OPERATORS_BY_TYPE.get(kind, ())
    if item.operator not in allowed:
        raise QueryError(
            f"operator {item.operator!r} does not apply to {item.dimension!r}, a {kind} dimension; "
            f"use one of {list(allowed)}"
        )
    if item.operator == "between":
        if len(item.values) != 2:
            raise QueryError("operator 'between' takes two values, the low and the high end")
    elif item.operator not in ("in", "not in") and len(item.values) != 1:
        raise QueryError(f"operator {item.operator!r} takes exactly one value")
    if kind == "time":
        reference = "{{ TimeDimension('" + item.dimension + "', 'day') }}"
        literals = [_literal(_iso_date(v, item.dimension)) for v in item.values]
        ordered = [_iso_date(v, item.dimension) for v in item.values]
    elif kind == "numeric":
        reference = "{{ Dimension('" + item.dimension + "') }}"
        numbers = [_number(v, item.dimension) for v in item.values]
        literals, ordered = [str(n) for n in numbers], numbers
    else:
        values = (known or {}).get(item.dimension)
        if values is not None and (unknown := [v for v in item.values if v not in values]):
            raise QueryError(
                f"{item.dimension!r} has no value {', '.join(map(repr, unknown))}; "
                f"its values are {values}"
            )
        reference = "{{ Dimension('" + item.dimension + "') }}"
        literals, ordered = [_literal(v) for v in item.values], []
    if item.operator == "between":
        if ordered[0] > ordered[1]:
            raise QueryError("operator 'between' takes the low end first, then the high end")
        return f"{reference} between {literals[0]} and {literals[1]}"
    if item.operator in ("in", "not in"):
        return f"{reference} {item.operator} ({', '.join(literals)})"
    operator = "<>" if item.operator == "!=" else item.operator
    return f"{reference} {operator} {literals[0]}"


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
    saved_query: str | None = None

    def resolved_metrics(self, catalog: Catalog) -> list[str]:
        """The metrics the query reads: its own, or its saved query's."""
        if self.saved_query is None:
            return self.metrics
        return list(catalog.saved_query(self.saved_query)["metrics"])

    def request(self, catalog: Catalog):  # -> MetricFlowQueryRequest
        from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

        if self.saved_query is not None:
            if self.metrics or self.group_by:
                raise QueryError(
                    f"saved query {self.saved_query!r} fixes its metrics and group-bys; send "
                    "metrics and group_by without saved_query to choose them"
                )
            saved = catalog.saved_query(self.saved_query)
            metrics, group_by = list(saved["metrics"]), list(saved["group_by"])
        else:
            metrics, group_by = self.metrics, self.group_by
        if not metrics:
            raise QueryError("name at least one metric")
        dimensions = catalog.dimensions(metrics)
        for name in group_by:
            if not _group_by_allowed(name, dimensions):
                raise QueryError(
                    f"cannot group by {name!r}; the dimensions are {sorted(dimensions)}"
                )
        allowed_order = set(metrics) | set(group_by)
        for name in self.order_by:
            if name.removeprefix("-") not in allowed_order:
                raise QueryError(f"can only order by a requested metric or group-by, not {name!r}")
        limit = min(self.limit or MAX_ROWS, MAX_ROWS)
        known = catalog.known_values(metrics)
        if self.saved_query is not None:
            # MetricFlow refuses metrics or group-bys beside a saved query; filters, dates, order
            # and limit narrow it.
            selection: dict[str, Any] = {"saved_query_name": self.saved_query}
        else:
            selection = {"metric_names": metrics, "group_by_names": group_by or None}
        return MetricFlowQueryRequest.create(
            **selection,
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
