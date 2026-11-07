"""The governed tables: which BigQuery tables the semantic layer's metrics are materialised into, and their words
(semantic/PLAN.md SL-24, #314).

SQL that cannot call MetricFlow (the semantic agent's fallback tool, #318, or a native data agent writing its own)
should not re-derive a metric; over the governed tables it only selects, filters and sums numbers MetricFlow
already computed. They are a plain dataset with descriptions any SQL engine reads, shaped for no one reader. This
module plans them from the semantic manifest and the dimensions MetricFlow lists per metric, with no warehouse and
no MetricFlow of its own:

- `<home>_daily`: the home semantic model's additive metrics (a sum or a count, and a derived metric that only adds
  or subtracts additive ones), one row per day (`metric_time__day`) and combination of the categorical dimensions
  every one of them has; any rows sum to the right number.
- `<home>_by_period`: the rest (ratios, distinct counts, averages, medians, balances, running totals, conversion
  rates, growth over a period), each MetricFlow's number for one whole day, ISO week or calendar month
  (`grain`, `period_start`), overall (`slice = 'total'`), or for one day and one value of one dimension (`slice`,
  `slice_value`); a row is read as it stands, never summed. Each column's description says how to get the
  metric over another span from the daily tables' additive columns, or that it has none.

A metric's home is its semantic model: a simple metric's own, any other's first input's (a ratio's numerator, a
cumulative or conversion metric's base). Names are the table's relation in dataset `governed`; the dbt model is
`gov_<name>`. build_governed.py writes the models from MetricFlow's compiled SQL; build_catalog.py lists the
tables in the agent catalog (their metrics' readiness products) and writes the governed data agent's context.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

DATASET = "governed"
PREFIX = "gov_"
TIME = "metric_time__day"
GRAINS = ("day", "week", "month")
TOTAL = "total"
# Aggregations whose values add up over days and over dimension values.
ADDITIVE_AGGS = {"sum", "count", "sum_boolean"}
# BigQuery's limit on a column description (persist_docs writes them).
COLUMN_DESCRIPTION_BYTES = 1024


@dataclass(frozen=True)
class Table:
    name: str
    kind: str  # "daily" or "by_period"
    home: str
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]

    @property
    def model(self) -> str:
        return PREFIX + self.name

    @property
    def relation(self) -> str:
        return f"{DATASET}.{self.name}"


def _words(text: str | None) -> str:
    return " ".join((text or "").split())


def _inputs(metric: dict) -> list[dict]:
    """The metrics a metric is computed from, with their filters and offsets."""
    params = metric["type_params"]
    if metric["type"] == "derived":
        return list(params["metrics"])
    if metric["type"] == "ratio":
        return [params["numerator"], params["denominator"]]
    if metric["type"] == "cumulative":
        return [params["cumulative_type_params"]["metric"]]
    if metric["type"] == "conversion":
        conversion = params["conversion_type_params"]
        return [conversion["base_metric"], conversion["conversion_metric"]]
    return []


def home(metric: dict, metrics: dict[str, dict]) -> str:
    """The semantic model a metric's governed table is named after."""
    aggregation = metric["type_params"].get("metric_aggregation_params")
    if aggregation:
        return aggregation["semantic_model"]
    return home(metrics[_inputs(metric)[0]["name"]], metrics)


LINEAR = re.compile(r"[\w\s()+-]*")


def additive(metric: dict, metrics: dict[str, dict]) -> bool:
    """Whether a metric's values add up over days and dimension values: a sum or a count without a non-additive
    dimension, or a derived metric that only adds and subtracts such metrics, none of them offset."""
    aggregation = metric["type_params"].get("metric_aggregation_params")
    if aggregation:
        return aggregation["agg"] in ADDITIVE_AGGS and not aggregation.get("non_additive_dimension")
    if metric["type"] != "derived":
        return False
    inputs = _inputs(metric)
    if any(item.get("offset_window") or item.get("offset_to_grain") or item.get("filter") for item in inputs):
        return False
    expr = re.sub(r"coalesce\((\w+), 0\)", r"\1", metric["type_params"]["expr"])
    return bool(LINEAR.fullmatch(expr)) and all(additive(metrics[item["name"]], metrics) for item in inputs)


def categorical(dimensions: list[dict]) -> set[str]:
    """The dimensions a governed table groups by: categorical ones; time dimensions other than the metric's own
    day and numeric ones (an amount: one row per order) stay with the semantic agent."""
    return {dimension["name"] for dimension in dimensions if dimension["type"] == "categorical"}


def plan(semantic_metrics: list[dict], dimensions: Callable[[str], list[dict]]) -> list[Table]:
    """The governed tables, sorted by name."""
    metrics = {metric["name"]: metric for metric in semantic_metrics}
    daily: dict[str, list[str]] = {}
    fixed: dict[str, list[str]] = {}
    derived: list[str] = []
    for name, metric in sorted(metrics.items()):
        if not additive(metric, metrics):
            fixed.setdefault(home(metric, metrics), []).append(name)
        elif metric["type"] == "derived":
            derived.append(name)
        else:
            daily.setdefault(home(metric, metrics), []).append(name)

    dims = {name: categorical(dimensions(name)) for name in metrics}
    tables: list[Table] = []
    shared = {owner: set.intersection(*(dims[name] for name in names)) for owner, names in daily.items()}
    alone = []
    for name in derived:
        owner = home(metrics[name], metrics)
        # A derived sum joins its home's table only when it has every dimension that table groups by.
        if owner in shared and shared[owner] <= dims[name]:
            daily[owner].append(name)
        else:
            alone.append(name)
    for owner, names in daily.items():
        tables.append(Table(f"{owner}_daily", "daily", owner, tuple(sorted(names)), tuple(sorted(shared[owner]))))
    for name in alone:
        owner = home(metrics[name], metrics)
        tables.append(Table(f"{name}_daily", "daily", owner, (name,), tuple(sorted(dims[name]))))
    for owner, names in fixed.items():
        common = set.intersection(*(dims[name] for name in names))
        tables.append(Table(f"{owner}_by_period", "by_period", owner, tuple(names), tuple(sorted(common))))
    return sorted(tables, key=lambda table: table.name)


def table_of(tables: list[Table], metric: str) -> Table:
    return next(table for table in tables if metric in table.metrics)


def _filter_columns(where: dict | None, table: Table) -> str | None:
    """An input's filter as a condition on a daily table's columns, or None when it names something else;
    '' for no filter."""
    if not where:
        return ""
    conditions = []
    for item in where.get("where_filters", []):
        sql = re.sub(r"\{\{\s*Dimension\('(\w+)'\)\s*\}\}", r"\1", item["where_sql_template"])
        if "{{" in sql or any(column not in table.dimensions for column in re.findall(r"\b(\w+__\w+)\b", sql)):
            return None
        conditions.append(sql)
    return " and ".join(conditions)


@dataclass(frozen=True)
class Component:
    """An input metric as an additive column of a daily table, with its filter as a condition on that table."""

    column: str
    table: Table
    condition: str


def component(item: dict, metrics: dict[str, dict], tables: list[Table]) -> Component | None:
    """An input metric's additive column, or None when it has none (not additive, or filtered on something
    its daily table does not hold)."""
    if not additive(metrics[item["name"]], metrics):
        return None
    table = table_of(tables, item["name"])
    condition = _filter_columns(item.get("filter"), table)
    return None if condition is None else Component(item["name"], table, condition)


def ratio_components(metric: dict, metrics: dict[str, dict], tables: list[Table]) -> tuple[Component, ...] | None:
    """A ratio's numerator and denominator as additive columns, or None when either has none."""
    if metric["type"] != "ratio":
        return None
    found = tuple(component(item, metrics, tables) for item in _inputs(metric))
    return None if None in found else found


def _summed(item: dict, metrics: dict[str, dict], tables: list[Table]) -> str | None:
    """`SUM(<column>)` of an input metric in its daily table, with its filter, or None without an additive form."""
    found = component(item, metrics, tables)
    if found is None:
        return None
    where = f" where {found.condition}" if found.condition else ""
    return f"SUM({found.column}) of {DATASET}.{found.table.name}{where}"


def combine(metric: dict, metrics: dict[str, dict], tables: list[Table]) -> str:
    """How to get a non-additive metric over a span that is not one row of its by-period table."""
    params = metric["type_params"]
    none = (
        "No additive form: read it from one row only, at the grain and slice asked; "
        "a span that is not one day, ISO week or calendar month is not available here."
    )
    if metric["type"] == "ratio":
        numerator, denominator = (_summed(item, metrics, tables) for item in _inputs(metric))
        if numerator and denominator:
            return (
                f"Over any other span or filter: {numerator} divided by {denominator}, "
                "each over the same days and dimension values."
            )
        return none
    if metric["type"] == "derived":
        words = {}
        for item in _inputs(metric):
            summed = _summed(item, metrics, tables)
            if not summed:
                return none
            offset = item.get("offset_window")
            later = f", {offset['count']} {offset['granularity']} earlier" if offset else ""
            words[item.get("alias") or item["name"]] = f"({summed}{later})"
        formula = re.sub(r"(?:coalesce\((\w+), 0\)|nullif\((\w+), 0\))", lambda m: m[1] or m[2], params["expr"])
        formula = re.sub(r"\b\w+\b", lambda m: words.get(m[0], m[0]), formula.replace(" * 1.0", ""))
        return f"Over another span: {formula}, each over the same span."
    if metric["type"] == "cumulative":
        cumulative = params["cumulative_type_params"]
        summed = _summed(cumulative["metric"], metrics, tables)
        if not summed:
            return none
        window = cumulative.get("window")
        if cumulative.get("grain_to_date"):
            span = f"from the first day of the {cumulative['grain_to_date']} to the day asked"
        elif window:
            span = f"over the {window['count']} {window['granularity']}s ending on the day asked"
        else:
            span = "over every day up to the day asked"
        return f"As of another day: {summed} {span}."
    aggregation = params.get("metric_aggregation_params") or {}
    if aggregation.get("non_additive_dimension"):
        return (
            "A balance: each period's row holds its last snapshot; never sum it over days or periods, "
            "and read the period's own row."
        )
    return none


def column_descriptions(table: Table, metrics: dict[str, dict], tables: list[Table], dimensions: dict) -> dict:
    """Every column of a governed table with its description: the metric's own words, then how it combines."""
    columns: dict[str, str] = {}
    if table.kind == "daily":
        columns[TIME] = "The day (UTC) the metrics on this row count, each metric's own time dimension."
    else:
        columns["grain"] = "The period's length: day, week (ISO, Monday to Sunday) or month."
        columns["period_start"] = "The period's first day."
        columns["slice"] = (
            f"'{TOTAL}' for the whole period, else (days only) the dimension the row breaks the metrics down by"
            + (f": one of {', '.join(table.dimensions)}." if table.dimensions else ".")
        )
        columns["slice_value"] = "The value of the slice's dimension on this row; NULL on a total row."
    if table.kind == "daily":
        for name in table.dimensions:
            columns[name] = _words(dimensions.get(name)) or f"The {name.replace('__', ' ')}."
    for name in table.metrics:
        metric = metrics[name]
        how = (
            "Additive: SUM it over any days and dimension values."
            if table.kind == "daily"
            else "Not additive: never SUM or AVG it over rows. " + combine(metric, metrics, tables)
        )
        columns[name] = f"{metric['label']}: {_words(metric['description'])} {how}"
    for name, text in columns.items():
        if len(text.encode()) > COLUMN_DESCRIPTION_BYTES:
            raise ValueError(f"{table.relation}.{name}: description over BigQuery's {COLUMN_DESCRIPTION_BYTES} bytes")
    return columns


def table_description(table: Table) -> str:
    if table.kind == "daily":
        grain = f"one row per day ({TIME})" + (
            f" and combination of {', '.join(table.dimensions)}" if table.dimensions else ""
        )
        return (
            f"Governed {table.home.replace('_', ' ')} metrics by day: {grain}, every number computed by MetricFlow "
            "from the semantic layer's definitions. Every metric column is additive: SUM it over any days and "
            "dimension values, and never re-derive a metric from other tables."
        )
    return (
        f"Governed {table.home.replace('_', ' ')} metrics that do not add up (ratios, distinct counts, averages, "
        "balances, running totals, conversion rates, growth), each computed by MetricFlow for one whole period: "
        "grain 'day', 'week' (ISO, from Monday) or 'month', starting on period_start; for the whole period "
        f"(slice '{TOTAL}') or, on days, for one value of one dimension (slice names it, slice_value holds it). "
        "Read a number from exactly one row and never SUM or AVG these columns over rows; for another span, "
        "each column's description says how to combine the daily tables' additive columns, or that it cannot."
    )
