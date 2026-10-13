import pytest
from pplk8s.dbt import STAGES, run_dbt


@pytest.mark.parametrize("stage", STAGES)
def test_operator_config(stage):
    op = run_dbt(stage, pipeline="sales")
    assert op.task_id == f"dbt_{stage}"
    assert op.arguments == ["build", "--select", f"tag:sales,tag:{stage}"]
    assert op.service_account_name == "dbt"
    assert op.on_finish_action == "delete_pod"
    assert op.get_logs is True
    assert op.name == f"dbt-sales-{stage}"
    assert op.labels["pplk8s/pipeline"] == "sales"
    assert op.random_name_suffix is True
    assert op.env_from[0].secret_ref.name == "warehouse-credentials"
    assert "workloads" in op.namespace
    assert op.container_resources.limits["memory"]
    assert op.retries == 2
    assert op.retry_exponential_backoff is True


def test_overrides_and_custom_task_id():
    op = run_dbt("gold", pipeline="sales", task_id="build_gold", retries=5, pool="dbt")
    assert op.task_id == "build_gold"
    assert op.retries == 5
    assert op.pool == "dbt"


def test_unknown_stage_is_rejected():
    with pytest.raises(ValueError):
        run_dbt("platinum", pipeline="sales")


@pytest.mark.parametrize("pipeline", ["", "Sales", "a,tag:b", "x y"])
def test_unsafe_pipeline_names_are_rejected(pipeline):
    with pytest.raises(ValueError):
        run_dbt("gold", pipeline=pipeline)


def test_pipeline_names_with_underscores_make_valid_pod_names():
    assert run_dbt("silver", pipeline="partner_returns").name == "dbt-partner-returns-silver"


def test_image_comes_only_from_the_dbt_image_variable():
    # No default tag: a missing Variable fails the task instead of running a stale image (D16).
    assert run_dbt("silver", pipeline="sales").image == "{{ var.value.dbt_image }}"


def test_namespace_is_overridable_by_variable():
    assert "var.value.get('dbt_namespace'" in run_dbt("silver", pipeline="sales").namespace


def test_pod_complies_with_restricted_profile():
    op = run_dbt("gold", pipeline="sales")
    assert op.security_context.run_as_non_root is True
    assert op.security_context.run_as_user == 10001
    assert op.security_context.seccomp_profile.type == "RuntimeDefault"
    assert op.container_security_context.allow_privilege_escalation is False
    assert op.container_security_context.read_only_root_filesystem is True
    assert op.container_security_context.capabilities.drop == ["ALL"]
    assert {m.mount_path for m in op.volume_mounts} == {"/dbt/target", "/dbt/logs", "/tmp"}
    assert {v.name for v in op.volumes} == {m.name for m in op.volume_mounts}
    assert op.automount_service_account_token is False


def test_vars_are_passed_as_one_json_argument():
    # Values may be Jinja: KPO renders `arguments`, so a DAG can template the data month (D36).
    month = "{{ data_interval_start.strftime('%Y-%m') }}"
    op = run_dbt("silver", pipeline="tlc", vars={"data_month": month})
    assert op.arguments == [
        "build",
        "--select",
        "tag:tlc,tag:silver",
        "--vars",
        '{"data_month": "{{ data_interval_start.strftime(\'%Y-%m\') }}"}',
    ]


def test_no_vars_leaves_the_command_unchanged():
    op = run_dbt("gold", pipeline="sales", vars=None)
    assert op.arguments == ["build", "--select", "tag:sales,tag:gold"]
