"""The semantic agent's only data tools: list, describe and query metrics (semantic/PLAN.md SL-2).

At work `DataAgentToolset.ask_data_agent` fills this seam; here MetricFlow does. Every tool returns
a dict, and a request the semantic layer cannot answer comes back as `{"error": ...}` for the model
to read, never as an exception that ends the turn.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from semantic_agent.metrics import Catalog, Filter, MetricQuery, QueryError, run


@cache
def catalog() -> Catalog:
    return Catalog.load()


def list_metrics() -> dict[str, Any]:
    """Lists every business metric the semantic layer defines, with its label and meaning.

    Call this first: an answer may only use these metrics.
    """
    return {
        "metrics": [
            {"name": m["name"], "label": m["label"], "description": m["description"]}
            for m in catalog().metrics.values()
        ]
    }


def describe_metric(name: str) -> dict[str, Any]:
    """Describes one metric: its definition, time grain, and the dimensions it can be grouped or
    filtered by.

    Args:
        name: The metric's name, as list_metrics returns it.
    """
    try:
        metric = catalog().metric(name)
    except QueryError as e:
        return {"error": str(e)}
    return {
        key: metric[key]
        for key in ("name", "label", "description", "type", "time_grain", "pipelines", "dimensions")
    }


def query_metrics(
    metrics: list[str],
    group_by: list[str] | None = None,
    filters: list[Filter] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    order_by: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Computes metrics through the semantic layer and returns their rows and the SQL it ran.

    Args:
        metrics: Metric names from list_metrics, e.g. ["revenue_eur"].
        group_by: Dimensions to break the metrics down by, e.g. ["metric_time__day"] for one row per
            day, ["metric_time__month"] per month, or ["order__status"]. Omit for one total row.
        filters: Conditions on categorical dimensions, e.g.
            [{"dimension": "order__currency", "operator": "=", "values": ["EUR"]}];
            operator is one of =, !=, in, not in.
        start_date: First day to include (YYYY-MM-DD), inclusive.
        end_date: Last day to include (YYYY-MM-DD), inclusive.
        order_by: Requested metrics or group-bys to sort by; prefix "-" for descending.
        limit: Maximum rows to return (at most 200).
    """
    query = MetricQuery(
        metrics=metrics,
        group_by=group_by or [],
        filters=[f if isinstance(f, Filter) else Filter.model_validate(f) for f in filters or []],
        start_date=start_date,
        end_date=end_date,
        order_by=order_by or [],
        limit=limit,
    )
    try:
        return run(query, catalog())
    except QueryError as e:
        return {"error": str(e)}


TOOLS = [list_metrics, describe_metric, query_metrics]
