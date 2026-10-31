"""The semantic agent's only data tools: list, describe and query metrics (semantic/PLAN.md SL-2).

At work `DataAgentToolset.ask_data_agent` fills this seam; here MetricFlow does. Every tool returns
a dict, and a request the semantic layer cannot answer comes back as `{"error": ...}` for the model
to read, never as an exception that ends the turn. Every query result carries the freshness of its
metrics' data (SL-4), with the sentence the answer quotes.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from semantic_agent.freshness import freshness
from semantic_agent.metrics import Catalog, Filter, MetricQuery, QueryError, run


@cache
def catalog() -> Catalog:
    return Catalog.load()


def list_metrics() -> dict[str, Any]:
    """Lists every business metric the semantic layer defines, with its label and meaning; the
    glossary: business terms that are not metrics, each with the metrics and dimensions it maps to;
    and the saved queries: recurring questions answered the same way every time, each a fixed set
    of metrics, group-bys and filters that query_metrics runs by name.

    Call this first: an answer may only use these metrics.
    """
    return {
        "metrics": [
            {"name": m["name"], "label": m["label"], "description": m["description"]}
            for m in catalog().metrics.values()
        ],
        "glossary": [
            {key: term[key] for key in ("term", "description", "synonyms", "metrics", "dimensions")}
            for term in catalog().glossary
        ],
        "saved_queries": [
            {key: query[key] for key in ("name", "question", "metrics", "group_by", "where")}
            for query in catalog().saved_queries.values()
        ],
    }


def describe_metric(name: str) -> dict[str, Any]:
    """Describes one metric: its definition, time grain, and the dimensions it can be grouped or
    filtered by, with the values of each categorical dimension that declares them: filter on one of
    those values exactly.

    Args:
        name: The metric's name, as list_metrics returns it.
    """
    try:
        metric = catalog().metric(name)
    except QueryError as e:
        return {"error": str(e)}
    return {
        key: metric[key]
        for key in (
            "name",
            "label",
            "description",
            "type",
            "time_grain",
            "pipelines",
            "readiness",
            "dimensions",
        )
    }


def query_metrics(
    metrics: list[str] | None = None,
    group_by: list[str] | None = None,
    filters: list[Filter] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    order_by: list[str] | None = None,
    limit: int | None = None,
    saved_query: str | None = None,
) -> dict[str, Any]:
    """Computes metrics through the semantic layer and returns their rows, the SQL it ran, and
    how fresh their data is: quote `freshness.statement` in the answer.

    Args:
        metrics: Metric names from list_metrics, e.g. ["revenue_eur"].
        group_by: Dimensions to break the metrics down by, e.g. ["metric_time__day"] for one row per
            day, ["metric_time__month"] per month, or ["order__status"]. Omit for one total row.
        filters: Conditions on categorical dimensions, e.g.
            [{"dimension": "order__currency", "operator": "=", "values": ["EUR"]}];
            operator is one of =, !=, in, not in. A value must be one describe_metric lists for
            the dimension, when it lists any.
        start_date: First day to include (YYYY-MM-DD), inclusive.
        end_date: Last day to include (YYYY-MM-DD), inclusive.
        order_by: Requested metrics or group-bys to sort by; prefix "-" for descending.
        limit: Maximum rows to return (at most 200).
        saved_query: A saved query's name from list_metrics, instead of metrics and group_by: it
            fixes them, and filters, dates, order_by and limit narrow it.
    """
    query = MetricQuery(
        metrics=metrics or [],
        group_by=group_by or [],
        filters=[f if isinstance(f, Filter) else Filter.model_validate(f) for f in filters or []],
        start_date=start_date,
        end_date=end_date,
        order_by=order_by or [],
        limit=limit,
        saved_query=saved_query,
    )
    try:
        result = run(query, catalog())
        names = query.resolved_metrics(catalog())
    except QueryError as e:
        return {"error": str(e)}
    products = sorted({p for name in names for p in catalog().metric(name).get("readiness", [])})
    # A saved query's metrics are not in the call's arguments, so the result names them (the audit).
    named = {"metrics": names} if saved_query is not None else {}
    return {**result, **named, "freshness": freshness(products)}


TOOLS = [list_metrics, describe_metric, query_metrics]
