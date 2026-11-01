"""The request the metric tools hand MetricFlow: checked against the catalog, never model SQL."""

import datetime

import pytest

from semantic_agent.metrics import (
    MAX_ROWS,
    Catalog,
    Filter,
    MetricQuery,
    QueryError,
    group_by_parameter,
    where_clause,
)
from tests.conftest import FIXTURES

CATALOG = Catalog.load(FIXTURES / "agent.json")
ORDER_DIMENSIONS = CATALOG.dimensions(["revenue_eur"])


def test_the_catalog_holds_every_metric_of_s2_and_every_domain():
    assert sorted(CATALOG.metrics) == [
        "acting_customers",
        "ad_clicks",
        "ad_spend_eur",
        "applications",
        "average_order_value_eur",
        "booking_value_eur",
        "bookings",
        "bookings_mtd",
        "bookings_wow_growth",
        "calls_labelled",
        "calls_with_objection",
        "cancellation_rate",
        "candidates_in_stage",
        "cart_sessions",
        "cart_to_checkout_rate",
        "checkout_sessions",
        "cost_per_booking_eur",
        "cost_per_lead_eur",
        "customer_actions",
        "customers_distinct",
        "customers_to_date",
        "damaged_return_share",
        "engaged_customers_28d",
        "engaged_customers_7d",
        "hires",
        "lead_to_booking_rate",
        "leads",
        "leads_mtd",
        "leads_wow_growth",
        "messages_replied",
        "messages_sent",
        "net_revenue_eur",
        "objection_rate",
        "orders_cancelled",
        "orders_total",
        "partners_engaged",
        "positive_calls",
        "positive_sentiment_share",
        "remaining_budget_eur",
        "repeat_customers",
        "repeat_revenue_share",
        "replies",
        "reply_rate",
        "return_rate",
        "returns_count",
        "returns_eur",
        "returns_on_order_date",
        "revenue_eur",
        "revenue_eur_mtd",
        "revenue_eur_wow_growth",
        "revenue_repeat_customers_eur",
        "signup_to_first_order_rate",
        "signups",
        "site_sessions",
        "time_to_hire_days",
        "view_to_cart_rate",
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
    "value", ["{{ 7*7 }}", "{% if 1 %}x{% endif %}", "{# note #}x", "EUR{{ undefined_thing }}"]
)
def test_a_filter_value_holding_a_jinja_delimiter_is_refused(value):
    """Issue #161: MetricFlow renders the where filter, so '{{ 7*7 }}' filtered on '49'."""
    item = Filter(dimension="order__currency", operator="in", values=["EUR", value])
    with pytest.raises(QueryError, match=r"holds a template delimiter.*plain text") as refused:
        where_clause(item, ORDER_DIMENSIONS, CATALOG.known_values(["revenue_eur"]))
    assert repr(value) in str(refused.value)


def test_braces_without_a_delimiter_stay_a_literal():
    item = Filter(dimension="order__currency", values=["{EUR} }}"])
    assert where_clause(item, ORDER_DIMENSIONS) == "{{ Dimension('order__currency') }} = '{EUR} }}'"


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
    assert [(p.name, getattr(p, "grain", None)) for p in request.group_by] == [
        ("metric_time", "month"),
        ("order__status", None),
    ]
    assert request.where_constraints == ["{{ Dimension('order__currency') }} = 'EUR'"]
    assert request.time_constraint_start == datetime.datetime(2026, 10, 1)
    [order] = request.order_by
    assert (order.order_by.name, order.descending) == ("revenue_eur", True)
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


def test_the_catalog_holds_the_saved_queries_with_their_questions():
    """Issue #164: the recurring questions live in dbt as saved queries, not beside the code."""
    assert sorted(CATALOG.saved_queries) == [
        "channel_performance",
        "daily_sales",
        "damaged_returns_daily",
        "net_sales_daily",
        "orders_by_status",
        "returns_by_reason",
        "sales_by_country_daily",
    ]
    damaged = CATALOG.saved_query("damaged_returns_daily")
    assert damaged["metrics"] == ["returns_count", "returns_eur"]
    assert damaged["group_by"] == ["metric_time__day"]
    assert damaged["where"] == ["{{ Dimension('return__reason') }} = 'damaged'"]
    assert damaged["question"].endswith("by day?")
    assert damaged["readiness"] == ["returns.silver"]


def test_a_saved_query_request_names_it_and_takes_dates_filters_and_order():
    query = MetricQuery(
        metrics=[],
        saved_query="daily_sales",
        filters=[Filter(dimension="order__status", values=["shipped"])],
        start_date="2026-10-02",
        end_date="2026-10-02",
        order_by=["-revenue_eur", "metric_time__day"],
        limit=5,
    )
    request = query.request(CATALOG)
    assert request.saved_query_name == "daily_sales"
    assert request.metric_names is None and request.group_by_names is None
    assert request.where_constraints == ["{{ Dimension('order__status') }} = 'shipped'"]
    assert request.time_constraint_end == datetime.datetime(2026, 10, 2)
    assert request.order_by_names == ["-revenue_eur", "metric_time__day"]
    assert query.resolved_metrics(CATALOG) == [
        "revenue_eur",
        "orders_total",
        "orders_cancelled",
        "customers_distinct",
    ]


@pytest.mark.parametrize(
    ("query", "message"),
    [
        (MetricQuery(metrics=[], saved_query="weekly_sales"), "no saved query named"),
        (MetricQuery(metrics=["leads"], saved_query="daily_sales"), "fixes its metrics"),
        (
            MetricQuery(metrics=[], group_by=["order__status"], saved_query="daily_sales"),
            "fixes its metrics and group-bys",
        ),
        (MetricQuery(metrics=[], saved_query="orders_by_status", order_by=["x"]), "order by"),
        (
            MetricQuery(
                metrics=[],
                saved_query="returns_by_reason",
                filters=[Filter(dimension="return__reason", values=["damaged goods"])],
            ),
            "its values are",
        ),
    ],
)
def test_a_saved_query_is_checked_like_any_request(query, message):
    with pytest.raises(QueryError, match=message):
        query.request(CATALOG)


def test_dbt_project_dir_comes_from_the_env_outside_the_repo(monkeypatch):
    """In the image the agents sit at /app/agents, with no repo around them (issue #111)."""
    from semantic_agent import metrics

    monkeypatch.setattr(metrics, "__file__", "/app/agents/semantic_agent/metrics.py")
    monkeypatch.setenv("DBT_PROJECT_DIR", "/app/dbt")
    assert str(metrics.project_dir()) == "/app/dbt"


# Time and numeric dimensions (a signup cohort, orders over an amount): each value is type-checked
# and rendered from its parsed form, never from the model's text.
@pytest.mark.parametrize(
    ("operator", "values", "expected"),
    [
        (
            ">=",
            ["2024-09-01"],
            "{{ TimeDimension('customer__signup_date', 'day') }} >= '2024-09-01'",
        ),
        (
            "<=",
            ["2024-09-30"],
            "{{ TimeDimension('customer__signup_date', 'day') }} <= '2024-09-30'",
        ),
        ("<", ["2024-09-30"], "{{ TimeDimension('customer__signup_date', 'day') }} < '2024-09-30'"),
        ("=", ["2024-09-01"], "{{ TimeDimension('customer__signup_date', 'day') }} = '2024-09-01'"),
        (
            "between",
            ["2024-09-01", "2024-09-30"],
            "{{ TimeDimension('customer__signup_date', 'day') }} "
            "between '2024-09-01' and '2024-09-30'",
        ),
    ],
)
def test_a_time_dimension_takes_comparisons_on_iso_dates(operator, values, expected):
    item = Filter(dimension="customer__signup_date", operator=operator, values=values)
    assert where_clause(item, CATALOG.dimensions(["revenue_eur"])) == expected


@pytest.mark.parametrize(
    ("operator", "values", "expected"),
    [
        (">", ["100"], "{{ Dimension('order__amount') }} > 100"),
        (">=", ["99.5"], "{{ Dimension('order__amount') }} >= 99.5"),
        ("<", ["-1"], "{{ Dimension('order__amount') }} < -1"),
        ("!=", ["25.00"], "{{ Dimension('order__amount') }} <> 25.00"),
        ("in", ["25", "45.0"], "{{ Dimension('order__amount') }} in (25, 45.0)"),
        ("between", ["10", "50"], "{{ Dimension('order__amount') }} between 10 and 50"),
    ],
)
def test_a_numeric_dimension_takes_comparisons_on_numbers(operator, values, expected):
    item = Filter(dimension="order__amount", operator=operator, values=values)
    assert where_clause(item, CATALOG.dimensions(["revenue_eur"])) == expected


def test_the_catalog_types_a_numeric_dimension():
    assert CATALOG.dimensions(["orders_total"])["order__amount"] == "numeric"
    assert CATALOG.dimensions(["orders_total"])["customer__signup_date"] == "time"


@pytest.mark.parametrize(
    ("item", "message"),
    [
        (Filter(dimension="customer__signup_date", operator=">=", values=["September"]), "a date"),
        (Filter(dimension="customer__signup_date", operator=">=", values=["2024-09"]), "a date"),
        (Filter(dimension="customer__signup_date", values=["2024-09-01 00:00"]), "a date"),
        (
            Filter(dimension="customer__signup_date", operator="in", values=["2024-09-01"]),
            "operator",
        ),
        (Filter(dimension="order__amount", operator=">", values=["a lot"]), "a number"),
        (Filter(dimension="order__amount", operator=">", values=["1e3"]), "a number"),
        (Filter(dimension="order__amount", operator=">", values=["NaN"]), "a number"),
        (Filter(dimension="order__amount", operator=">", values=["100 or 1=1"]), "a number"),
        (Filter(dimension="order__amount", operator=">", values=["1", "2"]), "exactly one value"),
        (Filter(dimension="order__amount", operator="between", values=["1"]), "two values"),
        (Filter(dimension="order__amount", operator="between", values=["50", "10"]), "low"),
        (
            Filter(
                dimension="customer__signup_date",
                operator="between",
                values=["2024-09-30", "2024-09-01"],
            ),
            "low",
        ),
        (Filter(dimension="order__status", operator=">", values=["placed"]), "operator"),
        (
            Filter(dimension="metric_time", operator=">=", values=["2026-10-01"]),
            "start_date and end_date",
        ),
    ],
)
def test_a_typed_filter_is_refused_unless_its_values_fit(item, message):
    with pytest.raises(QueryError, match=message):
        where_clause(
            item, CATALOG.dimensions(["revenue_eur"]), CATALOG.known_values(["revenue_eur"])
        )


@pytest.mark.parametrize(
    ("dimension", "operator"),
    [("customer__signup_date", ">="), ("order__amount", ">"), ("order__status", "=")],
)
@pytest.mark.parametrize("value", ["{{ 7*7 }}", "{% if 1 %}1{% endif %}", "{# x #}1"])
def test_a_jinja_delimiter_is_refused_for_every_value_type(dimension, operator, value):
    item = Filter(dimension=dimension, operator=operator, values=[value])
    with pytest.raises(QueryError, match="template delimiter"):
        where_clause(item, CATALOG.dimensions(["revenue_eur"]))


# Group-bys: a time grain, a date part and an entity become typed MetricFlow parameters,
# each from a name the catalog lists; anything else is refused naming what is allowed.
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("metric_time__week", ("metric_time", "week", None)),
        ("metric_time__extract_dow", ("metric_time", None, "dow")),
        ("customer__signup_date__extract_month", ("customer__signup_date", None, "month")),
        ("metric_time", ("metric_time", None, None)),
    ],
)
def test_a_time_group_by_is_a_typed_grain_or_date_part(name, expected):
    parameter = group_by_parameter(
        name, CATALOG.dimensions(["revenue_eur"]), CATALOG.entities(["revenue_eur"])
    )
    date_part = parameter.date_part.value if parameter.date_part else None
    assert (parameter.name, parameter.grain, date_part) == expected


@pytest.mark.parametrize(
    ("metric", "name"), [("revenue_eur", "customer"), ("ad_spend_eur", "campaign")]
)
def test_an_entity_the_catalog_lists_is_a_group_by(metric, name):
    assert name in CATALOG.entities([metric])
    parameter = group_by_parameter(name, CATALOG.dimensions([metric]), CATALOG.entities([metric]))
    assert parameter.name == name and not hasattr(parameter, "grain")


@pytest.mark.parametrize(
    ("metric", "name"),
    [
        ("revenue_eur", "campaign"),  # an entity, but not one orders reach
        ("revenue_eur", "metric_time__extract_week"),  # MetricFlow has no week date part
        ("revenue_eur", "metric_time__extract_hour"),
        ("revenue_eur", "order__status__extract_dow"),  # a date part of a categorical dimension
        ("revenue_eur", "metric_time__dow"),
    ],
)
def test_a_group_by_outside_the_catalog_is_refused_naming_the_allowed_ones(metric, name):
    with pytest.raises(QueryError, match=r"cannot group by .*__extract_dow.*entities are"):
        group_by_parameter(name, CATALOG.dimensions([metric]), CATALOG.entities([metric]))


def test_top_three_campaigns_by_spend_orders_and_limits_by_the_metric():
    request = MetricQuery(
        metrics=["ad_spend_eur"], group_by=["campaign"], order_by=["-ad_spend_eur"], limit=3
    ).request(CATALOG)
    [group] = request.group_by
    [order] = request.order_by
    assert group.name == "campaign"
    assert (order.order_by.name, order.descending, request.limit) == ("ad_spend_eur", True, 3)


def test_ordering_by_a_date_part_orders_by_its_typed_parameter():
    request = MetricQuery(
        metrics=["revenue_eur"],
        group_by=["metric_time__extract_dow"],
        order_by=["metric_time__extract_dow"],
    ).request(CATALOG)
    [order] = request.order_by
    assert order.order_by is request.group_by[0] and not order.descending


# A metric defined for BigQuery only is disabled on Postgres: the catalog lists it as not available
# here, and the tools decline it by name rather than answer with something else.
def test_a_bigquery_only_metric_is_declined_on_postgres_naming_its_warehouse():
    assert "median_order_value_eur" not in CATALOG.metrics
    with pytest.raises(QueryError, match=r"defined only on bigquery.*not available here"):
        CATALOG.metric("median_order_value_eur")
    with pytest.raises(QueryError, match="not available here"):
        MetricQuery(metrics=["median_order_value_eur"]).request(CATALOG)


# The time spine's custom grains (the fiscal calendar) are grains like month, from the catalog.
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("metric_time__fiscal_quarter", ("metric_time", "fiscal_quarter")),
        ("customer__signup_date__fiscal_year", ("customer__signup_date", "fiscal_year")),
    ],
)
def test_a_custom_grain_the_catalog_lists_is_a_time_grain(name, expected):
    assert CATALOG.custom_grains == ["fiscal_quarter", "fiscal_year"]
    parameter = group_by_parameter(
        name,
        CATALOG.dimensions(["revenue_eur"]),
        CATALOG.entities(["revenue_eur"]),
        CATALOG.custom_grains,
    )
    assert (parameter.name, parameter.grain) == expected


def test_a_custom_grain_is_refused_when_the_catalog_has_none():
    with pytest.raises(QueryError, match="cannot group by"):
        group_by_parameter("metric_time__fiscal_quarter", CATALOG.dimensions(["revenue_eur"]), [])


def test_a_request_groups_by_the_fiscal_quarter():
    request = MetricQuery(
        metrics=["revenue_eur"], group_by=["metric_time__fiscal_quarter"]
    ).request(CATALOG)
    assert [(p.name, p.grain) for p in request.group_by] == [("metric_time", "fiscal_quarter")]
