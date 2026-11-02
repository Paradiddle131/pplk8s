"""BigQuery's rules that the emulator and a plain parse let through, over compiled dbt SQL (#104, #275).

Usage: python bigquery_sql_rules.py <dir of compiled .sql files>
Every file must parse as BigQuery (sqlglot), use none of the Postgres spellings the dialect macros replace, and
cast to no parameterized type: BigQuery refuses `CAST(x AS NUMERIC(12, 2))` ("Parameterized types are not allowed
in CAST expressions", measured on the lab project), where the goccy emulator and sqlglot accept it; a view
holding one is created, then fails every query (#275). Prints one line per problem; exits 1 on any, or on no file.
"""

from __future__ import annotations

import pathlib
import re
import sys

import sqlglot
from sqlglot import exp

# Postgres spellings the dialect macros replace; sqlglot alone reads some of them leniently.
POSTGRES_ONLY = re.compile(r"at time zone|generate_series\(|timestamptz|::| as text\)", re.IGNORECASE)
# A reserved word as a bare column name, after `AS` or a dot: BigQuery refuses it ("Unexpected keyword ORDER"),
# sqlglot accepts it. MetricFlow 0.213 names an entity's column after the entity, unquoted (`order_id AS order`),
# so a governed model that groups by an order's dimension did (SL-24, measured on the lab project 2026-11-02). The
# reserved words that are also type names (array, enum, interval, proto, struct) are left out: `CAST(x AS ...)`.
RESERVED_NAME = re.compile(
    r"(?:\b[Aa][Ss]\s+|\.)(all|and|any|as|asc|assert_rows_modified|at|between|by|case|cast|collate|contains|create|"
    r"cross|cube|current|default|define|desc|distinct|else|end|escape|except|exclude|exists|extract|false|fetch|"
    r"following|for|from|full|group|grouping|groups|hash|having|if|ignore|in|inner|intersect|into|is|join|lateral|"
    r"left|like|limit|lookup|merge|natural|new|no|not|null|nulls|of|on|or|order|outer|over|partition|preceding|"
    r"qualify|range|recursive|respect|right|rollup|rows|select|set|some|tablesample|then|to|treat|true|unbounded|"
    r"union|unnest|using|when|where|window|with|within)\b(?!`)"
)


def problems(name: str, sql: str) -> list[str]:
    sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    found = []
    try:
        statements = sqlglot.parse(sql, read="bigquery", error_level=sqlglot.ErrorLevel.RAISE)
    except sqlglot.errors.ParseError as e:
        return [f"{name}: {str(e).splitlines()[0][:120]}"]
    if match := POSTGRES_ONLY.search(sql):
        found.append(f"{name}: Postgres-only {match[0]!r}")
    if match := RESERVED_NAME.search(sql):
        found.append(f"{name}: a reserved word as an unquoted name, BigQuery refuses it: {match[0]!r}")
    for statement in filter(None, statements):
        for cast in statement.find_all(exp.Cast):
            if cast.to.expressions:
                found.append(f"{name}: a parameterized type in CAST, BigQuery refuses it: {cast.sql()[:100]}")
    return found


def main(directory: str) -> int:
    files = [f for f in sorted(pathlib.Path(directory).rglob("*.sql")) if ".yml" not in str(f)]
    bad = [p for f in files for p in problems(f.name, f.read_text())]
    print("\n".join(bad) or f"{len(files)} compiled files keep BigQuery's rules")
    return 1 if bad or not files else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
