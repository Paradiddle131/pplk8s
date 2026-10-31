"""The MetricFlow Python surface the agent and the catalog generator reuse from the `mf` CLI.

dbt documents only the `mf` commands; `MetricFlowEngine` and its request and result types have no
public reference, so these tests pin what this repo calls (semantic/PLAN.md § 5, risks). They run
offline, with no warehouse and no `dbt parse`, so a MetricFlow bump that moves the surface fails
`make agent-test` naming it, instead of failing at runtime in the pod or the image build.

The callers: `semantic_agent/metrics.py` (`engine`, `MetricQuery.request`, `run`) and
`dbt/scripts/build_catalog.py` (`_metricflow`). `mf query` (`dbt_metricflow/cli/main.py`) builds the
same `MetricFlowQueryRequest.create(...)` and calls `MetricFlowEngine.query` or `.explain`.
"""

import dataclasses
import importlib.metadata
import inspect

import pytest

from semantic_agent import metrics
from semantic_agent.metrics import Filter, MetricQuery
from tests.conftest import FIXTURES

SURFACE = "the MetricFlow Python surface (semantic/PLAN.md § 5)"


def test_the_licence_is_apache_from_0_209_0_on():
    """metricflow 0.150.0 to 0.208.2 were BUSL; 0.209.0 and later are Apache-2.0 (SL-1)."""
    version = importlib.metadata.version("metricflow")
    release = tuple(int(part) for part in version.split(".")[:3])
    assert release >= (0, 209, 0), f"metricflow {version} is below 0.209.0, BUSL-licensed"
    assert importlib.metadata.metadata("metricflow")["License-Expression"] == "Apache-2.0"


def test_the_symbols_import():
    from dbt_metricflow.cli.cli_configuration import CLIConfiguration  # noqa: F401
    from metricflow.engine.metricflow_engine import (  # noqa: F401
        MetricFlowEngine,
        MetricFlowExplainResult,
        MetricFlowQueryRequest,
        MetricFlowQueryResult,
    )


def test_the_engine_is_set_up_as_the_cli_sets_it_up():
    from dbt_metricflow.cli.cli_configuration import CLIConfiguration
    from metricflow.engine.metricflow_engine import MetricFlowEngine

    setup = inspect.signature(CLIConfiguration.setup).parameters
    assert {"dbt_project_path", "dbt_profiles_path"} <= setup.keys(), SURFACE
    for attribute in ("semantic_manifest_lookup", "sql_client"):
        assert hasattr(CLIConfiguration, attribute), f"CLIConfiguration.{attribute}: {SURFACE}"
    engine = inspect.signature(MetricFlowEngine.__init__).parameters
    assert {"semantic_manifest_lookup", "sql_client"} <= engine.keys(), SURFACE
    for method in ("query", "explain", "simple_dimensions_for_metrics"):
        assert callable(getattr(MetricFlowEngine, method, None)), f"engine.{method}: {SURFACE}"


def test_every_keyword_the_agent_passes_is_one_create_accepts(monkeypatch):
    """`MetricQuery.request` with every part set: each keyword binds to the real signature."""
    from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

    signature = inspect.signature(MetricFlowQueryRequest.create)
    sent: dict = {}

    def create(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr(MetricFlowQueryRequest, "create", create)
    query = MetricQuery(
        metrics=["orders_total"],
        group_by=["metric_time__day", "order__status"],
        filters=[Filter(dimension="order__status", values=["cancelled"])],
        start_date="2026-10-01",
        end_date="2026-10-02",
        order_by=["-orders_total"],
        limit=5,
    )
    query.request(metrics.Catalog.load(FIXTURES / "agent.json"))
    unknown = sorted(sent.keys() - signature.parameters.keys())
    assert not unknown, f"MetricFlowQueryRequest.create no longer takes {unknown}: {SURFACE}"
    assert {"metric_names", "group_by_names", "where_constraints", "order_by_names"} <= sent.keys()


def test_the_catalog_generator_keywords_are_ones_create_accepts():
    """build_catalog.py's compiled SQL request: one metric per day, ordered by day."""
    from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

    parameters = inspect.signature(MetricFlowQueryRequest.create).parameters
    assert {"metric_names", "group_by_names", "order_by_names"} <= parameters.keys(), SURFACE


@pytest.mark.parametrize(
    ("owner", "attribute"),
    [
        ("MetricFlowQueryResult", "sql"),
        ("MetricFlowQueryResult", "result_df"),
        ("MetricFlowDataTable", "column_names"),
        ("MetricFlowDataTable", "rows"),
        ("MetricFlowExplainResult", "sql_statement"),
    ],
)
def test_the_results_carry_what_the_callers_read(owner, attribute):
    from metricflow.data_table.mf_table import MetricFlowDataTable
    from metricflow.engine.metricflow_engine import MetricFlowExplainResult, MetricFlowQueryResult

    cls = {
        "MetricFlowQueryResult": MetricFlowQueryResult,
        "MetricFlowDataTable": MetricFlowDataTable,
        "MetricFlowExplainResult": MetricFlowExplainResult,
    }[owner]
    fields = {f.name for f in dataclasses.fields(cls)} if dataclasses.is_dataclass(cls) else set()
    assert attribute in fields or hasattr(cls, attribute), f"{owner}.{attribute}: {SURFACE}"


def test_an_explained_statement_carries_its_sql():
    from metricflow.engine.metricflow_engine import MetricFlowExplainResult
    from metricflow.execution.execution_plan import SqlStatement

    returned = inspect.signature(MetricFlowExplainResult.sql_statement.fget).return_annotation
    assert "SqlStatement" in str(returned), SURFACE
    fields = {f.name for f in dataclasses.fields(SqlStatement)}
    assert "sql" in fields or hasattr(SqlStatement, "sql"), f"SqlStatement.sql: {SURFACE}"
