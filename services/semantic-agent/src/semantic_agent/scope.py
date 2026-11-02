"""Which rows the agent's identity may read, said in every answer that depends on it (SL-21).

A scoped role (ops.agent_scopes, the stand-in for BigQuery row access policies) reads only its
countries' customers and their orders and returns; the warehouse enforces it with row policies,
so MetricFlow's queries need no change. A total over those rows reads like the company's total, so
the scope must reach the answer: `scope()` returns, for a role that has one, its countries, the
tables a row policy limits and one `statement` the agent quotes, built here from the warehouse and
the SQL that computed the figure, never by the model.

A figure is scoped when the SQL that computed it read a limited table; one that read none covers
every country, and one whose SQL is not in the result may or may not be scoped, which is said.

Env: dbt's own `DBT_*` connection variables, as freshness.py, so the scope is read as the role the
metrics are read as.
"""

from __future__ import annotations

import os
import re
from typing import Any

import psycopg

SQL = """
select ops.agent_countries(current_user::name) as countries,
       array(select n.nspname || '.' || c.relname
               from pg_class c join pg_namespace n on n.oid = c.relnamespace
              where c.relrowsecurity and c.relkind in ('r', 'p')
              order by 1) as tables
"""


def _url() -> str:
    env = os.environ.get
    user, password = env("DBT_USER", "warehouse"), env("DBT_PASSWORD", "warehouse")
    host, port = env("DBT_HOST", "warehouse"), env("DBT_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{env('DBT_DBNAME', 'warehouse')}"


def tables_read(sql: str, tables: list[str]) -> list[str]:
    """The tables of `tables` (schema.table) that `sql` names, quoted or not, with or without the
    database in front."""
    found = []
    for table in tables:
        schema, name = table.split(".", 1)
        pattern = rf'(?<![\w$]){re.escape(schema)}"?\s*\.\s*"?{re.escape(name)}(?![\w$])'
        if re.search(pattern, sql, re.IGNORECASE):
            found.append(table)
    return found


def assess(countries: list[str] | None, tables: list[str], sql: str | None) -> dict[str, Any] | None:
    """The scope of one answer, or None when the role reads every row."""
    if not countries:
        return None
    where = ", ".join(countries)
    if sql is None:
        read = None
        statement = (
            f"Scope unknown: this agent reads only the rows of customers in {where} in "
            f"{', '.join(tables) or 'no table yet'}, and the result does not show which tables "
            "this figure read."
        )
    else:
        read = tables_read(sql, tables)
        statement = (
            f"Scoped: this figure counts only customers in {where} ({', '.join(read)}), the "
            "rows this agent may read, not the whole company."
            if read
            else f"Not scoped: this figure read no table limited to {where}, so it covers "
            "every country."
        )
    return {"countries": countries, "tables": tables, "read": read, "statement": statement}


def lookup() -> tuple[list[str] | None, list[str]]:
    """The role's countries (None: unscoped) and the tables a row policy limits; raises
    psycopg.Error when the warehouse cannot say."""
    with psycopg.connect(_url(), connect_timeout=10) as conn:
        row = conn.execute(SQL).fetchone()
    assert row is not None
    return row[0], list(row[1])


def scope(sql: str | None) -> dict[str, Any] | None:
    """The scope of an answer whose figure `sql` computed; an unreadable scope is said, not
    raised, since an answer from a scoped role must never read as the company's."""
    try:
        countries, tables = lookup()
    except psycopg.Error as e:
        reason = str(e).strip().splitlines()[0]
        return {
            "countries": None,
            "tables": [],
            "read": None,
            "statement": f"Scope unknown: the agent's row scope could not be read ({reason}), "
            "so this figure may cover only some countries.",
        }
    return assess(countries, tables, sql)
