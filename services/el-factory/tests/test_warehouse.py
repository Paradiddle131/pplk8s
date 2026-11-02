"""The warehouse seam (el_factory/warehouse.py, SL-19): the selector, which module and driver it
imports, and every psycopg error as a WarehouseError that says whether a retry can help."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

import psycopg
import pytest

from el_factory import warehouse_postgres
from el_factory.config import Config, ConfigError
from el_factory.model import Table
from el_factory.warehouse import WarehouseError, warehouse
from tests.conftest import make_config

TABLE = Table("orders", (("order_id", "text"),))


# The selector.


def test_postgres_is_the_default():
    config = Config.from_env({"WAREHOUSE_DSN": "postgresql://w"})

    chosen = warehouse(config)

    assert config.warehouse == "postgres"
    assert isinstance(chosen, warehouse_postgres.PostgresWarehouse)


def test_an_unknown_warehouse_is_refused_at_boot():
    with pytest.raises(ConfigError, match="ELF_WAREHOUSE='snowflake' is not one of postgres"):
        Config.from_env({"ELF_WAREHOUSE": "snowflake", "WAREHOUSE_DSN": "postgresql://w"})


def test_a_missing_driver_names_the_extra_to_install(monkeypatch):
    monkeypatch.setitem(sys.modules, "el_factory.warehouse_postgres", None)

    with pytest.raises(WarehouseError, match="needs the 'postgres' extra of el-factory") as e:
        warehouse(make_config())

    assert e.value.transient is False


def test_the_app_imports_no_driver_until_a_warehouse_is_chosen():
    """gunicorn imports el_factory.app before it calls create_app_from_env(): the driver comes in
    with the chosen implementation, so an image without it can still import the app (SL-19)."""
    code = (
        "import json, sys\n"
        "import el_factory.app\n"
        "from el_factory.config import Config\n"
        "from el_factory.warehouse import warehouse\n"
        "before = 'psycopg' in sys.modules\n"
        "warehouse(Config.from_env({'WAREHOUSE_DSN': 'postgresql://w'}))\n"
        "print(json.dumps([before, 'psycopg' in sys.modules]))\n"
    )
    env = {k: v for k, v in os.environ.items() if k != "ELF_WAREHOUSE"}
    out = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )

    assert json.loads(out.stdout) == [False, True]


# Postgres: psycopg's errors leave as WarehouseError.


class Cursor:
    def __init__(self, error: Exception | None) -> None:
        self.error = error

    def __enter__(self) -> Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, *args: Any) -> None:
        if self.error is not None:
            raise self.error


class Connection(Cursor):
    def cursor(self) -> Cursor:
        return Cursor(self.error)


def connect_raising(error: Exception, *, at_connect: bool):
    def connect(dsn: str) -> Connection:
        if at_connect:
            raise error
        return Connection(error)

    return connect


@pytest.mark.parametrize(
    ("error", "at_connect", "transient"),
    [
        (psycopg.OperationalError("connection refused"), True, True),
        (psycopg.OperationalError("server closed the connection unexpectedly"), False, True),
        (psycopg.errors.SerializationFailure("could not serialize access"), False, True),
        (psycopg.errors.UndefinedTable('relation "ds_source.orders" does not exist'), False, False),
        (psycopg.errors.InsufficientPrivilege("permission denied for schema"), False, False),
    ],
)
def test_psycopg_errors_are_warehouse_errors(monkeypatch, error, at_connect, transient):
    monkeypatch.setattr(
        warehouse_postgres.psycopg, "connect", connect_raising(error, at_connect=at_connect)
    )

    with pytest.raises(WarehouseError) as e:
        warehouse_postgres.PostgresWarehouse("postgresql://w").ensure_table(TABLE)

    assert e.value.transient is transient
    assert e.value.__cause__ is error
    assert str(e.value) == str(error)


def test_other_errors_pass_through_unchanged(monkeypatch):
    """An error that is not the warehouse's (here a bug in the caller) keeps its own type."""
    monkeypatch.setattr(
        warehouse_postgres.psycopg,
        "connect",
        connect_raising(KeyError("order_id"), at_connect=False),
    )

    with pytest.raises(KeyError):
        warehouse_postgres.PostgresWarehouse("postgresql://w").ensure_table(TABLE)
