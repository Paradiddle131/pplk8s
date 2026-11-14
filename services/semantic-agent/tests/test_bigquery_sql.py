"""Reserved-word names in MetricFlow's BigQuery SQL (semantic_agent/bigquery_sql.py, #322): quoted
after `AS ` and after a `.`, everything else left as it is, and the agent's engine quoting on
BigQuery only."""

from __future__ import annotations

import dataclasses

import pytest
from metricflow.protocols.sql_client import SqlEngine
from metricflow.sql.render.sql_plan_renderer import SqlPlanRenderResult

from semantic_agent import metrics
from semantic_agent.bigquery_sql import QuotingSqlClient, quote_reserved

# MetricFlow 0.213's SQL for returns_count by order__status, as the lab project refused it.
METRICFLOW_SQL = """\
SELECT
  orders_src_10000.status AS order__status
  , SUM(subq_1.__returns_count) AS returns_count
FROM (
  -- Read Elements From Semantic Model 'returns'
  SELECT
    order_id AS order
    , CASE WHEN return_id IS NOT NULL THEN 1 ELSE 0 END AS __returns_count
  FROM `pplk8s-lab`.`silver`.`returns` returns_src_10000
) subq_1
LEFT OUTER JOIN
  `pplk8s-lab`.`silver`.`orders` orders_src_10000
ON
  subq_1.order = orders_src_10000.order_id
GROUP BY
  order__status
LIMIT 200
"""


def test_a_reserved_word_after_as_is_quoted():
    assert quote_reserved("SELECT order_id AS order FROM t") == "SELECT order_id AS `order` FROM t"


def test_a_reserved_word_after_a_dot_is_quoted():
    assert quote_reserved("ON subq_1.order = o.order_id") == "ON subq_1.`order` = o.order_id"


def test_metricflows_query_has_both_names_quoted_and_nothing_else_changed():
    quoted = quote_reserved(METRICFLOW_SQL)
    assert "order_id AS `order`\n" in quoted
    assert "subq_1.`order` = orders_src_10000.order_id" in quoted
    assert quoted.replace("`order`", "order") == METRICFLOW_SQL


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT status AS order__status, o.status, o.order_id FROM t AS orders",  # not reserved
        "SELECT x FROM t ORDER BY x LIMIT 1",  # a keyword where SQL puts one
        "SELECT CAST(x AS STRUCT<a INT64>) AS s",  # MetricFlow's keywords are capitals
        "SELECT x.amount_eur, 1.5 AS one_and_a_half",  # a decimal is not a name
    ],
)
def test_a_name_that_is_not_a_lower_case_reserved_word_is_untouched(sql):
    assert quote_reserved(sql) == sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT order_id AS `order` FROM t",
        "ON subq_1.`order` = o.order_id",
        "FROM `project`.`silver`.`order`",
    ],
)
def test_an_already_quoted_name_is_untouched(sql):
    assert quote_reserved(sql) == sql
    assert quote_reserved(quote_reserved(sql)) == sql


@pytest.mark.parametrize(
    "sql",
    [
        "WHERE note = 'shipped AS order'",
        "WHERE note = 'v.order'",
        'WHERE note = "x.end"',
        "WHERE note = 'it\\'s AS order'",
        "-- Pass Only Elements: AS order, x.order\nSELECT 1",
        "/* subq.order */ SELECT 1",
    ],
)
def test_a_literal_or_a_comment_is_untouched(sql):
    assert quote_reserved(sql) == sql


@dataclasses.dataclass
class Renderer:
    sql: str

    def render_sql_plan(self, sql_plan):
        return SqlPlanRenderResult(sql=self.sql, bind_parameter_set=sql_plan)

    @property
    def expr_renderer(self):
        return "expressions"


class Client:
    def __init__(self, engine_type: SqlEngine, sql: str = METRICFLOW_SQL) -> None:
        self.sql_engine_type = engine_type
        self.sql_plan_renderer = Renderer(sql)
        self.ran: list[str] = []

    def query(self, stmt, sql_bind_parameter_set=None):
        self.ran.append(stmt)
        return "table"


def test_metricflows_render_result_is_a_dataclass_with_its_sql():
    """The surface QuotingSqlClient relies on: a render result it can replace the `sql` of."""
    assert dataclasses.is_dataclass(SqlPlanRenderResult)
    assert "sql" in {f.name for f in dataclasses.fields(SqlPlanRenderResult)}


def test_the_quoting_client_renders_quoted_sql_and_delegates_the_rest():
    client = QuotingSqlClient(Client(SqlEngine.BIGQUERY))
    rendered = client.sql_plan_renderer.render_sql_plan("params")
    assert rendered.sql == quote_reserved(METRICFLOW_SQL)
    assert rendered.bind_parameter_set == "params"
    assert client.sql_plan_renderer.expr_renderer == "expressions"
    assert client.sql_engine_type is SqlEngine.BIGQUERY
    assert client.query(rendered.sql) == "table"
    assert client.ran == [quote_reserved(METRICFLOW_SQL)]


@pytest.mark.parametrize(
    ("engine_type", "quoted"), [(SqlEngine.BIGQUERY, True), (SqlEngine.POSTGRES, False)]
)
def test_the_agents_engine_quotes_on_bigquery_only(monkeypatch, engine_type, quoted):
    from dbt_metricflow.cli import cli_configuration
    from metricflow.engine import metricflow_engine

    client = Client(engine_type)

    class Config:
        semantic_manifest_lookup = "lookup"
        sql_client = client

        def setup(self, **_):
            pass

    monkeypatch.setattr(cli_configuration, "CLIConfiguration", Config)
    monkeypatch.setattr(metricflow_engine, "MetricFlowEngine", lambda **kwargs: kwargs)
    metrics.engine.cache_clear()
    try:
        built = metrics.engine()
    finally:
        metrics.engine.cache_clear()
    assert built["semantic_manifest_lookup"] == "lookup"
    assert isinstance(built["sql_client"], QuotingSqlClient) is quoted
    rendered = built["sql_client"].sql_plan_renderer.render_sql_plan(None).sql
    assert ("order_id AS `order`" in rendered) is quoted
