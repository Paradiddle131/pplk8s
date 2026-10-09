import pytest
from pplk8s.dbt import STAGES, run_dbt


@pytest.mark.parametrize("stage", STAGES)
def test_operator_config(stage):
    op = run_dbt(stage)
    assert op.task_id == f"dbt_{stage}"
    assert op.arguments == ["build", "--select", stage]
    assert op.service_account_name == "dbt"
    assert op.on_finish_action == "delete_pod"
    assert op.get_logs is True
    assert op.name == f"dbt-{stage}"
    assert op.random_name_suffix is True
    assert op.env_from[0].secret_ref.name == "warehouse-credentials"
    assert "localhost:5001/dbt:0.1.0" in op.image
    assert "workloads" in op.namespace
    assert op.container_resources.limits["memory"]
    assert op.retries == 2
    assert op.retry_exponential_backoff is True


def test_overrides_and_custom_task_id():
    op = run_dbt("gold", task_id="build_gold", retries=5, pool="dbt")
    assert op.task_id == "build_gold"
    assert op.retries == 5
    assert op.pool == "dbt"


def test_unknown_stage_is_rejected():
    with pytest.raises(ValueError):
        run_dbt("platinum")


def test_image_and_namespace_are_overridable_by_variables():
    op = run_dbt("silver")
    assert "var.value.get('dbt_image'" in op.image
    assert "var.value.get('dbt_namespace'" in op.namespace
