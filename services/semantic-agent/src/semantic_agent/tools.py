"""The semantic agent's only data tools: list, describe and query metrics (semantic/PLAN.md SL-2).

At work `DataAgentToolset.ask_data_agent` fills this seam; here MetricFlow does. Every tool returns
a dict, and a request the semantic layer cannot answer comes back as `{"error": ...}` for the model
to read, never as an exception that ends the turn. A query result names the metrics it ran; the
agent's after-tool callback (guard.py), not this toolset, attaches their freshness (SL-4) and
audits the call (SL-10), so both survive a swap of the toolset (#177).
"""

from __future__ import annotations

from functools import cache
from typing import Any

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
    """Describes one metric: its definition, time grain, the dimensions it can be grouped or
    filtered by, with the values of each categorical dimension that declares them (filter on one of
    those values exactly), and the entities it can be grouped by (one row per id).

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
            "entities",
        )
        if key in metric
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
    """Computes metrics through the semantic layer and returns their rows, the SQL it ran, the
    metrics it computed, and how fresh their data is: quote `freshness.statement` in the answer.

    Args:
        metrics: Metric names from list_metrics, e.g. ["revenue_eur"].
        group_by: Dimensions to break the metrics down by, e.g. ["metric_time__day"] for one row per
            day, ["metric_time__month"] per month, or ["order__status"]. Omit for one total row.
            A date part groups by a piece of the date across periods:
            ["metric_time__extract_dow"] for one row per weekday (1 is Monday, 7 Sunday), or
            __extract_month, __extract_day, __extract_quarter, __extract_year, __extract_doy.
            An entity describe_metric lists, e.g. ["campaign"], gives one row per id; with
            order_by and limit it answers "top 3 campaigns by spend".
        filters: Conditions on dimensions, e.g.
            [{"dimension": "order__currency", "operator": "=", "values": ["EUR"]}].
            A categorical dimension takes =, !=, in, not in, with a value describe_metric lists
            for it, when it lists any. A time dimension (signup cohort) takes =, !=, >, >=, <, <=
            or between on dates like 2024-09-01, e.g. {"dimension": "customer__signup_date",
            "operator": "between", "values": ["2024-09-01", "2024-09-30"]}. A numeric dimension
            takes those and in, not in on numbers, e.g. {"dimension": "order__amount",
            "operator": ">", "values": ["100"]}. between takes the low end, then the high end,
            both included.
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
    # A saved query's metrics are not in the call's arguments, so the result names them: the
    # metrics its freshness is looked up for and its audit row holds.
    return {**result, "metrics": names}


TOOLS = [list_metrics, describe_metric, query_metrics]

CATALOG_TOOLS = ("list_metrics", "describe_metric")
"""The tools that read only the catalog; every other tool is a data tool, audited and given its
metrics' freshness. At work: `list_accessible_data_agents` and `get_data_agent_info`."""
