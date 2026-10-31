"""The request the metric tools hand MetricFlow: checked against the catalog, never model SQL."""

import datetime

import pytest

from semantic_agent.metrics import MAX_ROWS, Catalog, Filter, MetricQuery, QueryError, where_clause
from tests.conftest import FIXTURES

CATALOG = Catalog.load(FIXTURES / "agent.json")
ORDER_DIMENSIONS = CATALOG.dimensions(["revenue_eur"])


def test_the_catalog_holds_every_metric_of_s2_and_marketing():
    assert sorted(CATALOG.metrics) == [
        "ad_clicks",
        "ad_spend_eur",
        "booking_value_eur",
        "bookings",
        "cancellation_rate",
        "cost_per_booking_eur",
        "cost_per_lead_eur",
        "customers_distinct",
        "lead_to_booking_rate",
        "leads",
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


def test_a_categorical_dimension_carries_the_values_its_column_declares():
    known = CATALOG.known_values(["returns_eur"])
    assert "damaged" in known["return__reason"]
    assert known["order__status"] == ["placed", "shipped", "cancelled"]
    assert "order__currency" not in known  # declares no values, so any value is passed on


@pytest.mark.parametrize(
    ("operator", "values"),
    [("=", ["damaged goods"]), ("!=", ["Damaged"]), ("in", ["damaged", "broken"])],
)
def test_a_value_the_dimension_does_not_declare_is_refused_with_the_ones_it_does(operator, values):
    item = Filter(dimension="return__reason", operator=operator, values=values)
    dimensions = CATALOG.dimensions(["returns_eur"])
    with pytest.raises(
        QueryError, match=r"'return__reason' has no value .*its values are \[.*'damaged'"
    ):
        where_clause(item, dimensions, CATALOG.known_values(["returns_eur"]))


def test_a_declared_value_and_a_dimension_without_declared_values_pass():
    dimensions = CATALOG.dimensions(["returns_eur"])
    known = CATALOG.known_values(["returns_eur"])
    assert where_clause(Filter(dimension="return__reason", values=["damaged"]), dimensions, known)
    assert where_clause(Filter(dimension="order__currency", values=["XYZ"]), dimensions, known)


def test_a_request_with_a_guessed_value_never_reaches_metricflow():
    query = MetricQuery(
        metrics=["returns_eur"],
        filters=[Filter(dimension="return__reason", values=["damaged goods"])],
    )
    with pytest.raises(QueryError, match="its values are"):
        query.request(CATALOG)


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
            Filter(dimension="campaign__channel", values=["search"]),
            "cannot filter by 'campaign__channel'",
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
        (MetricQuery(metrics=["revenue_eur"], group_by=["campaign__channel"]), "cannot group by"),
        (MetricQuery(metrics=["revenue_eur"], group_by=["order__status__day"]), "cannot group by"),
        (MetricQuery(metrics=["revenue_eur"], order_by=["amount"]), "can only order by"),
        (MetricQuery(metrics=["revenue_eur"], start_date="last week"), "must be a date"),
    ],
)
def test_requests_outside_the_catalog_are_refused(query, message):
    with pytest.raises(QueryError, match=message):
        query.request(CATALOG)


def test_dbt_project_dir_comes_from_the_env_outside_the_repo(monkeypatch):
    """In the image the agents sit at /app/agents, with no repo around them (issue #111)."""
    from semantic_agent import metrics

    monkeypatch.setattr(metrics, "__file__", "/app/agents/semantic_agent/metrics.py")
    monkeypatch.setenv("DBT_PROJECT_DIR", "/app/dbt")
    assert str(metrics.project_dir()) == "/app/dbt"
