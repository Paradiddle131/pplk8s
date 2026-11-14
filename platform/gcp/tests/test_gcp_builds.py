"""check_gcp_builds.py on the real dbt and agent builds and on copies that would ship Postgres or TLC to GCP (SL-19)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

GCP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GCP))

from check_gcp_builds import ROOT, problems


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    for context in ("dbt", "services/semantic-agent", "services/el-factory"):
        shutil.copytree(
            ROOT / context,
            tmp_path / context,
            ignore=shutil.ignore_patterns(
                "target", "logs", "dbt_packages", ".venv", "__pycache__", ".*_cache"
            ),
            symlinks=True,
        )
    return tmp_path


AGENT = "services/semantic-agent"
ELF = "services/el-factory"


def test_the_repo_ships_no_postgres_and_no_tlc() -> None:
    assert problems() == []


def test_a_tlc_model_outside_the_package_fails(copy: Path) -> None:
    (copy / "dbt" / "models" / "gold" / "gld_tlc_extra.sql").write_text("select 1\n")
    assert problems(copy) == [
        "dbt: the bigquery build copies the TLC path dbt/models/gold/gld_tlc_extra.sql",
        "semantic-agent: the bigquery build copies the TLC path dbt/models/gold/gld_tlc_extra.sql",
    ]


def test_the_package_itself_stays_out(copy: Path) -> None:
    assert problems(copy) == []
    dockerfile = copy / "dbt" / "Dockerfile"
    dockerfile.write_text(dockerfile.read_text().replace(" --exclude=packages ", " "))
    assert any("dbt/packages/tlc/" in p for p in problems(copy))


def test_a_postgres_package_in_the_lock_fails(copy: Path) -> None:
    lock = copy / "dbt" / "requirements-bigquery.txt"
    lock.write_text(lock.read_text() + "psycopg2-binary==2.9.10\n")
    assert problems(copy) == [
        "dbt: dbt/requirements-bigquery.txt holds the Postgres package psycopg2-binary"
    ]


def test_a_stale_lock_fails(copy: Path) -> None:
    top = copy / "dbt" / "requirements-bigquery.in"
    top.write_text(
        top.read_text().replace("dbt-bigquery==1.12.1", "dbt-bigquery==1.12.2")
    )
    assert any("recompile it" in p for p in problems(copy))


def test_the_copy_passes(copy: Path) -> None:
    assert problems(copy) == []


def test_a_postgres_package_in_the_agents_lock_fails(copy: Path) -> None:
    lock = copy / AGENT / "requirements-bigquery.txt"
    lock.write_text(lock.read_text() + "asyncpg==0.31.0\n")
    found = problems(copy)
    assert (
        f"semantic-agent: {AGENT}/requirements-bigquery.txt holds the Postgres package asyncpg"
        in found
    )
    assert any("differs from `uv export" in p for p in found)


def test_a_package_the_builds_leave_out_fails(copy: Path) -> None:
    lock = copy / AGENT / "requirements-bigquery.txt"
    lock.write_text(lock.read_text() + "pyarrow==22.0.0\n")
    assert (
        f"semantic-agent: {AGENT}/requirements-bigquery.txt holds pyarrow, which"
        " dbt/requirements-bigquery.exclude leaves out"
    ) in problems(copy)


def test_an_export_stale_against_uv_lock_fails(copy: Path) -> None:
    lock = copy / AGENT / "requirements-bigquery.txt"
    lock.write_text(lock.read_text().replace("litellm==1.96.2", "litellm==1.96.1"))
    stale = (
        f"semantic-agent: {AGENT}/requirements-bigquery.txt differs from `uv export --frozen"
        " --no-default-groups --extra bigquery --no-emit-project` of uv.lock: re-export it with"
        " `-o requirements-bigquery.txt`"
    )
    assert problems(copy) == [stale]


def test_the_agents_postgres_implementation_stays_out(copy: Path) -> None:
    dockerfile = copy / AGENT / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace("--exclude=warehouse_postgres.py ", "")
    )
    assert problems(copy) == [
        f"semantic-agent: {AGENT}/Dockerfile has no COPY --exclude in stage bigquery"
    ]


def test_the_agents_postgres_implementation_is_a_postgres_only_path(copy: Path) -> None:
    dockerfile = copy / AGENT / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            "--exclude=warehouse_postgres.py ", "--exclude=*.pyc "
        )
    )
    path = f"{AGENT}/src/semantic_agent/warehouse_postgres.py"
    assert problems(copy) == [
        f"semantic-agent: the bigquery build copies the Postgres-only path {path}"
    ]


def test_a_tlc_path_from_the_dbt_context_fails(copy: Path) -> None:
    dockerfile = copy / AGENT / "Dockerfile"
    text = dockerfile.read_text()
    marker = "COPY src/services.py /app/agents/services.py\n"
    dockerfile.write_text(
        text.replace(
            marker, marker + "COPY --from=dbt packages/tlc /app/dbt/packages/tlc\n"
        )
    )
    found = problems(copy)
    assert found and all(
        p.startswith(
            "semantic-agent: the bigquery build copies the TLC path dbt/packages/tlc/"
        )
        for p in found
    )


def test_the_postgres_stage_may_copy_tlc(copy: Path) -> None:
    """The TLC COPYs of the local stage are not the GCP build's."""
    assert "packages/tlc" in (copy / AGENT / "Dockerfile").read_text()
    assert problems(copy) == []


def test_el_factorys_file_sources_stay_out(copy: Path) -> None:
    dockerfile = copy / ELF / "Dockerfile"
    dockerfile.write_text(dockerfile.read_text().replace("--exclude=tlc ", ""))
    found = problems(copy)
    assert found and all(
        p.startswith(
            f"el-factory: the bigquery build copies the TLC path {ELF}/src/el_factory/tlc/"
        )
        for p in found
    )


def test_a_tlc_module_outside_el_factorys_package_fails(copy: Path) -> None:
    (copy / ELF / "src" / "el_factory" / "tlc_extra.py").write_text("")
    assert problems(copy) == [
        f"el-factory: the bigquery build copies the TLC path {ELF}/src/el_factory/tlc_extra.py"
    ]


def test_el_factorys_postgres_implementation_stays_out(copy: Path) -> None:
    dockerfile = copy / ELF / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace("--exclude=warehouse_postgres.py ", "")
    )
    path = f"{ELF}/src/el_factory/warehouse_postgres.py"
    assert problems(copy) == [
        f"el-factory: the bigquery build copies the Postgres-only path {path}"
    ]


def test_pyarrow_or_psycopg_in_el_factorys_lock_fails(copy: Path) -> None:
    lock = copy / ELF / "requirements-bigquery.txt"
    lock.write_text(lock.read_text() + "pyarrow==21.0.0\npsycopg==3.3.6\n")
    found = problems(copy)
    assert (
        f"el-factory: {ELF}/requirements-bigquery.txt holds the Postgres package psycopg"
        in found
    )
    assert (
        f"el-factory: {ELF}/requirements-bigquery.txt holds pyarrow, which"
        " dbt/requirements-bigquery.exclude leaves out"
    ) in found
    assert any(
        p.startswith("el-factory:") and "differs from `uv export" in p for p in found
    )
