"""MetricFlow's BigQuery SQL made runnable: reserved-word names backticked (#322, SL-24).

MetricFlow 0.213 writes keywords in capitals and an entity's column under the entity's own name,
unquoted: the entity `order` becomes `order_id AS order` and `subq_1.order`, which BigQuery refuses
("Syntax error: Unexpected keyword ORDER", measured on the lab project 2026-11-02 and 2026-11-06).
A lower-case GoogleSQL reserved word after `AS ` or a `.` is such a name, and `quote_reserved`
backticks it; string literals, backticked names and comments are left as they are.

The one place this is done, on the BigQuery path of the warehouse seam: the agent's MetricFlow
engine renders its SQL through `QuotingSqlClient` when dbt's target is BigQuery (metrics.py), and
`dbt/scripts/build_governed.py` quotes the governed tables' models with `quote_reserved`. This
module imports only the standard library, so build_governed.py loads it by its path, outside the
agent's package (whose `__init__` imports ADK). `tests/e2e/lib/bigquery_sql_rules.py` refuses any
compiled model that still holds such a name (`make bigquery-check`).
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any

# GoogleSQL's reserved keywords (https://cloud.google.com/bigquery/docs/reference/standard-sql/lexical#reserved_keywords).
RESERVED = frozenset(
    re.findall(
        r"\w+",
        """
        all and any array as asc assert_rows_modified at between by case cast collate contains
        create cross cube current default define desc distinct else end enum escape except
        exclude exists extract false fetch following for from full group grouping groups hash
        having if ignore in inner intersect interval into is join lateral left like limit lookup
        merge natural new no not null nulls of on or order outer over partition preceding proto
        qualify range recursive respect right rollup rows select set some struct tablesample
        then to treat true unbounded union unnest using when where window with within
        """,
    )
)
# A name MetricFlow writes: after `AS ` (an alias) or after a `.` (a column of a subquery).
NAME_AFTER = re.compile(r"(?<=\bAS )(\w+)\b|(?<=\.)(\w+)\b")
# What is not SQL text to rewrite: string literals, backticked names and comments.
UNTOUCHED = re.compile(
    r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`[^`]*`|--[^\n]*|/\*.*?\*/", re.DOTALL
)


def _quote_names(text: str) -> str:
    def quoted(match: re.Match[str]) -> str:
        name = match[0]
        return f"`{name}`" if name in RESERVED else name

    return NAME_AFTER.sub(quoted, text)


def quote_reserved(sql: str) -> str:
    """MetricFlow's SQL with every name it writes as a lower-case reserved word backticked."""
    parts, last = [], 0
    for kept in UNTOUCHED.finditer(sql):
        parts += [_quote_names(sql[last : kept.start()]), kept[0]]
        last = kept.end()
    return "".join([*parts, _quote_names(sql[last:])])


class _QuotingRenderer:
    """A MetricFlow SQL plan renderer whose rendered SQL has its reserved-word names quoted."""

    def __init__(self, renderer: Any) -> None:
        self._renderer = renderer

    def __getattr__(self, name: str) -> Any:
        return getattr(self._renderer, name)

    def render_sql_plan(self, sql_plan: Any) -> Any:
        rendered = self._renderer.render_sql_plan(sql_plan)
        return dataclasses.replace(rendered, sql=quote_reserved(rendered.sql))


class QuotingSqlClient:
    """MetricFlow's SQL client on BigQuery, its plan renderer quoting reserved-word names, so the
    SQL MetricFlow runs, explains and returns as `sql` is the same, quoted, statement."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._renderer = _QuotingRenderer(client.sql_plan_renderer)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    @property
    def sql_plan_renderer(self) -> Any:
        return self._renderer
