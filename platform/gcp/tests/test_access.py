"""access.yaml against the lab: the datasets dbt builds and the roles of dbt/macros/agent_warehouse.sql.

The lab's Postgres roles are the rehearsal of the lab project's service accounts (option A of
docs/semantic-layer-on-bigquery.md); a grant added on one side and not the other fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

GCP = Path(__file__).resolve().parent.parent
REPO = GCP.parent.parent
ACCESS = yaml.safe_load((GCP / "access.yaml").read_text())
MACRO = (REPO / "dbt" / "macros" / "agent_warehouse.sql").read_text()
SCHEMA_GRANT = re.compile(
    r"GRANT SELECT ON ALL TABLES IN SCHEMA ([a-z_, ]+) TO ([a-z_]+);"
)


def schema_reads(role: str) -> set[str]:
    """The schemas whose every table the lab role may read."""
    return {
        s.strip()
        for schemas, grantee in SCHEMA_GRANT.findall(MACRO)
        if grantee == role
        for s in schemas.split(",")
    }


def accounts_for(role: str) -> list[dict]:
    return [a for a in ACCESS["service_accounts"].values() if a["lab_role"] == role]


def dbt_schemas() -> set[str]:
    project = (REPO / "dbt" / "dbt_project.yml").read_text()
    return set(re.findall(r"^\s*\+schema:\s*([a-z_]+)\s*$", project, re.MULTILINE))


def source_schemas() -> set[str]:
    sources = yaml.safe_load((REPO / "dbt" / "models" / "sources.yml").read_text())
    return {s["schema"] for s in sources["sources"]}


def test_the_semantic_agent_reads_what_agent_metrics_reads() -> None:
    (agent,) = accounts_for("agent_metrics")
    assert (
        set(agent["reads"]) == schema_reads("agent_metrics") == {"silver", "semantic"}
    )
    assert agent["writes"] == []


def test_the_audit_writer_holds_no_dataset_grant() -> None:
    # agent_audit may only insert into ops.agent_queries: a table grant (#209), never a dataset's.
    (audit,) = accounts_for("agent_audit")
    assert audit["reads"] == audit["writes"] == []
    assert schema_reads("agent_audit") == set()
    assert "GRANT INSERT ON ops.agent_queries TO agent_audit;" in MACRO


def test_the_baseline_has_no_account() -> None:
    # The text-to-SQL baseline runs only inside the eval (SL-5), so agent_sql is never deployed.
    assert accounts_for("agent_sql") == []
    assert schema_reads("agent_sql") == {"gold", "exposed"}


def test_every_agent_role_exists_in_the_lab() -> None:
    for account in ACCESS["service_accounts"].values():
        if account["lab_role"] != "warehouse":
            assert f"CREATE ROLE {account['lab_role']} LOGIN" in MACRO


def test_the_datasets_are_what_dbt_builds_and_reads() -> None:
    # Plus `ops`: no model builds there, but dbt's run-operations create its tables (the agents' audit,
    # agent_warehouse; the freshness verdicts, source_freshness_table). The root project only: the TLC
    # package, whose sources read ops.file_versions, never reaches GCP (semantic/PLAN.md SL-19).
    assert set(ACCESS["datasets"]) == dbt_schemas() | source_schemas() | {"ops"}


def test_dbt_writes_its_layers_and_reads_the_landing_dataset() -> None:
    (runner,) = accounts_for("warehouse")
    assert set(runner["writes"]) == dbt_schemas() | {"ops"}
    assert set(runner["reads"]) == source_schemas() - {"ops"}


def test_every_grant_names_a_declared_dataset() -> None:
    for account in ACCESS["service_accounts"].values():
        assert set(account["reads"]) | set(account["writes"]) <= set(ACCESS["datasets"])
        assert not set(account["reads"]) & set(account["writes"])


TABLE_GRANT = re.compile(r"GRANT (SELECT|INSERT) ON (ops\.[a-z_]+) TO ([a-z_]+);")
ACCESS_FOR = {"SELECT": "read", "INSERT": "insert"}


def table_grants(role: str) -> dict[str, str]:
    """The lab role's table-level grants, as access.yaml spells them."""
    return {
        table: ACCESS_FOR[privilege]
        for privilege, table, grantee in TABLE_GRANT.findall(MACRO)
        if grantee == role
    }


def test_the_semantic_agent_reads_the_two_freshness_tables() -> None:
    (agent,) = accounts_for("agent_metrics")
    assert (
        agent["tables"]
        == table_grants("agent_metrics")
        == {"ops.readiness": "read", "ops.product_deadlines": "read"}
    )


def test_the_audit_writer_inserts_into_the_audit_table_and_nothing_else() -> None:
    (audit,) = accounts_for("agent_audit")
    assert (
        audit["tables"]
        == table_grants("agent_audit")
        == {"ops.agent_queries": "insert"}
    )


def test_table_grants_are_in_ops_and_read_or_insert() -> None:
    # infra/bigquery.tf grants on the ops tables tofu.sh finds; another dataset's table would never be granted.
    for account in ACCESS["service_accounts"].values():
        for table, access in (account.get("tables") or {}).items():
            assert table.split(".")[0] == "ops"
            assert access in {"read", "insert"}


def test_insert_is_data_editor_on_the_table_and_says_so() -> None:
    # BigQuery IAM has no insert-only role (tables.updateData also allows UPDATE and DELETE).
    bigquery = (GCP / "infra" / "bigquery.tf").read_text()
    assert 'insert = "roles/bigquery.dataEditor"' in bigquery
    assert 'read = "roles/bigquery.dataViewer"' in bigquery
    assert "cannot express insert-only" in (GCP / "access.yaml").read_text()
