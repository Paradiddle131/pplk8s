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
    assert set(ACCESS["datasets"]) == dbt_schemas() | source_schemas()


def test_dbt_writes_its_layers_and_reads_the_landing_dataset() -> None:
    (runner,) = accounts_for("warehouse")
    assert set(runner["writes"]) == dbt_schemas() | {"ops"}
    assert set(runner["reads"]) == source_schemas() - {"ops"}


def test_every_grant_names_a_declared_dataset() -> None:
    for account in ACCESS["service_accounts"].values():
        assert set(account["reads"]) | set(account["writes"]) <= set(ACCESS["datasets"])
        assert not set(account["reads"]) & set(account["writes"])
