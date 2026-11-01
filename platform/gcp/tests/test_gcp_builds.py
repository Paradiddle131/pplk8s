"""check_gcp_builds.py on the real dbt build and on copies that would ship Postgres or TLC to GCP (SL-19)."""

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
    shutil.copytree(
        ROOT / "dbt",
        tmp_path / "dbt",
        ignore=shutil.ignore_patterns("target", "logs", "dbt_packages"),
        symlinks=True,
    )
    return tmp_path


def test_the_repo_ships_no_postgres_and_no_tlc() -> None:
    assert problems() == []


def test_a_tlc_model_outside_the_package_fails(copy: Path) -> None:
    (copy / "dbt" / "models" / "gold" / "gld_tlc_extra.sql").write_text("select 1\n")
    assert problems(copy) == [
        "dbt: the bigquery build copies the TLC path dbt/models/gold/gld_tlc_extra.sql"
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
