"""The request the metric tools hand MetricFlow: checked against the catalog, never model SQL."""

import datetime

import pytest

from semantic_agent.metrics import MAX_ROWS, Catalog, Filter, MetricQuery, QueryError, where_clause
from tests.conftest import FIXTURES

CATALOG = Catalog.load(FIXTURES / "agent.json")
ORDER_DIMENSIONS = CATALOG.dimensions(["revenue_eur"])


def test_the_catalog_holds_every_metric_of_s2():
    assert sorted(CATALOG.metrics) == [
        "cancellation_rate",
        "customers_distinct",
        "net_revenue_eur",
        "orders_cancelled",
        "orders_total",
        "returns_count",
        "returns_eur",
        "revenue_eur",
    ]


def test_an_unknown_metric_names_the_ones_that_exist():
    with pytest.raises(QueryError, match="no metric named 'average_basket_eur'.*revenue_eur"):
        CATALOG.metric("average_basket_eur")


def test_dimensions_are_the_ones_every_requested_metric_shares():
    assert CATALOG.dimensions(["returns_count"]).keys() >= {"metric_time", "return__reason"}
    shared = CATALOG.dimensions(["revenue_eur", "returns_count"])
    assert "return__reason" not in shared
    assert shared["metric_time"] == "time"


def test_a_filter_value_is_a_quoted_literal_whatever_it_holds():
    clause = where_clause(
        Filter(dimension="order__status", values=["x' or 1=1; drop table silver.orders; --"]),
        ORDER_DIMENSIONS,
    )
    assert clause == (
        "{{ Dimension('order__status') }} = 'x'' or 1=1; drop table silver.orders; --'"
    )


@pytest.mark.parametrize(
    ("operator", "values", "expected"),
    [
        ("!=", ["cancelled"], "{{ Dimension('order__status') }} <> 'cancelled'"),
        ("in", ["placed", "shipped"], "{{ Dimension('order__status') }} in ('placed', 'shipped')"),
        ("not in", ["cancelled"], "{{ Dimension('order__status') }} not in ('cancelled')"),
    ],
)
def test_filter_operators(operator, values, expected):
    item = Filter(dimension="order__status", operator=operator, values=values)
    assert where_clause(item, ORDER_DIMENSIONS) == expected


@pytest.mark.parametrize(
    ("item", "message"),
    [
        (
            Filter(dimension="customer__country", values=["NL"]),
            "cannot filter by 'customer__country'",
        ),
        (Filter(dimension="metric_time", values=["2026-10-01"]), "start_date and end_date"),
        (Filter(dimension="order__status", values=[]), "has no values"),
        (Filter(dimension="order__status", values=["a", "b"]), "exactly one value"),
    ],
)
def test_filters_outside_the_catalog_are_refused(item, message):
    with pytest.raises(QueryError, match=message):
        where_clause(item, ORDER_DIMENSIONS)


def test_a_request_carries_the_checked_parts():
    request = MetricQuery(
        metrics=["revenue_eur"],
        group_by=["metric_time__month", "order__status"],
        filters=[Filter(dimension="order__currency", values=["EUR"])],
        start_date="2026-10-01",
        end_date="2026-10-31",
        order_by=["-revenue_eur"],
        limit=10_000,
    ).request(CATALOG)
    assert request.metric_names == ["revenue_eur"]
    assert request.group_by_names == ["metric_time__month", "order__status"]
    assert request.where_constraints == ["{{ Dimension('order__currency') }} = 'EUR'"]
    assert request.time_constraint_start == datetime.datetime(2026, 10, 1)
    assert request.order_by_names == ["-revenue_eur"]
    assert request.limit == MAX_ROWS


@pytest.mark.parametrize(
    ("query", "message"),
    [
        (MetricQuery(metrics=[]), "at least one metric"),
        (MetricQuery(metrics=["revenue_eur"], group_by=["customer__country"]), "cannot group by"),
        (MetricQuery(metrics=["revenue_eur"], group_by=["order__status__day"]), "cannot group by"),
        (MetricQuery(metrics=["revenue_eur"], order_by=["amount"]), "can only order by"),
        (MetricQuery(metrics=["revenue_eur"], start_date="last week"), "must be a date"),
    ],
)
def test_requests_outside_the_catalog_are_refused(query, message):
    with pytest.raises(QueryError, match=message):
        query.request(CATALOG)
