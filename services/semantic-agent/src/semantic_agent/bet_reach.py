"""Which setups can reach the data each case needs (#446; RULE.md § The arms, the reach policy).

A case's data is the warehouse tables its expected SQL reads (every turn's). A setup reaches a case
when every such table is in its reach, as each setup's builder or published context declares it:

- the SQL setups of ours, `baseline` and `custom-hybrid`'s fallback: `gold`, `exposed`, `legacy`,
  `silver` and the fiscal calendar (#445's grant);
- `native-mcp` and its Claude Code mirror: every dataset of the project;
- Google's data agents: their published tables (`388_parity.py --agents`; the context family's 16
  `silver` tables, `semantic.time_spine` and `legacy`, the narrower agents fewer);
- the MetricFlow setups read metrics, never tables: they reach a case some metric answers, the
  `covered` group, and the setups with arithmetic (#400) the `composable` group too.

A case out of a setup's reach is a reach limit (RULE.md § Retiring a defective case): its runs stay
scored, and the report labels them as such. A setup with no declared reach here
(`native-governed`, which reads governed views, `custom-toolbox`'s generated tools) is unlabelled.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from semantic_agent.evaluation import Question

TABLE = re.compile(r"\b(silver|gold|exposed|legacy|semantic|governed)\.([a-z_0-9]+)\b")

# The data agents' published silver tables (388_parity.py --agents, 2026-11-06; the main track's
# context in dbt/target/catalog/data_agent/context.json; probes/329_shaped_agent.TABLES and
# probes/331_graph_agent.TABLES).
CONTEXT_SILVER = frozenset(
    {
        "ad_spend", "applications", "bookings", "call_signals", "campaign_budgets", "campaigns",
        "candidate_days", "candidate_stages", "customer_actions", "customers", "leads", "orders",
        "outreach_messages", "outreach_replies", "partners", "returns",
    }
)  # fmt: skip
KC_SILVER = frozenset(
    {"orders", "customers", "returns", "ad_spend", "leads", "bookings", "campaigns"}
)
GRAPH_SILVER = frozenset({"orders", "customers", "returns"})
TIME_SPINE = ("semantic", "time_spine")


def _silver(tables: frozenset[str], spine: bool):
    def reach(schema: str, table: str) -> bool:
        if schema == "legacy":
            return True
        if (schema, table) == TIME_SPINE:
            return spine
        return schema == "silver" and table in tables

    return reach


def _sql(schema: str, table: str) -> bool:
    return schema in ("gold", "exposed", "legacy", "silver") or (schema, table) == TIME_SPINE


TABLE_REACH = {
    "baseline": _sql,
    "custom-hybrid": _sql,
    "native-mcp": lambda schema, table: True,
    "cc-native-mcp": lambda schema, table: True,
    **{
        arm: _silver(CONTEXT_SILVER, True)
        for arm in (
            "native-context",
            "native-context-bare",
            "native-context-python",
            "native-kc-max",
            "native-bare",
            "native-kc-reach",
        )
    },
    "native-kc": _silver(KC_SILVER, False),
    "native-shaped": _silver(KC_SILVER, False),
    "native-graph": _silver(GRAPH_SILVER, False),
}
# The metric setups: the groups some metric (or arithmetic over metrics) answers.
METRIC_REACH = {
    "custom-metricflow": ("covered",),
    "cc-metricflow": ("covered",),
    "custom-lightdash": ("covered",),
    "custom-metricflow-compute": ("covered", "composable"),
    "cc-metricflow-compute": ("covered", "composable"),
}
SETUPS = (*TABLE_REACH, *METRIC_REACH)


# Each derived table's `silver` sources, from dbt's manifest (`write_lineage`), cached beside the
# logs so the map needs no dbt build: a setup that reads those sources can rebuild the table, as the
# data agents do from `silver`.
LINEAGE = "lineage.json"


def write_lineage(manifest: Path, directory: Path) -> Path:
    data = json.loads(manifest.read_text())
    nodes = {
        k: v
        for k, v in data["nodes"].items()
        if v["resource_type"] in ("model", "seed", "snapshot")
    }

    def name(v: Mapping) -> str:
        return f"{v['schema']}.{v.get('alias') or v['name']}"

    def sources(key: str, seen: set[str]) -> set[str]:
        v = nodes[key]
        if v["schema"] == "silver" or (v["schema"], v.get("alias")) == TIME_SPINE:
            return {name(v)}
        out: set[str] = set()
        for dep in (v.get("depends_on") or {}).get("nodes") or []:
            if dep in nodes and dep not in seen:
                seen.add(dep)
                out |= sources(dep, seen)
        return out

    lineage = {
        name(v): sorted(sources(k, {k}))
        for k, v in nodes.items()
        if v["schema"] in ("gold", "exposed", "governed", "semantic")
    }
    path = directory / LINEAGE
    path.write_text(json.dumps(lineage, indent=0, sort_keys=True) + "\n")
    return path


def read_lineage(directory: Path) -> dict[str, list[str]]:
    path = directory / LINEAGE
    return json.loads(path.read_text()) if path.exists() else {}


def tables(question: Question) -> set[tuple[str, str]]:
    """The tables a case's expected SQL reads, over all its turns."""
    return {m for t in question.turns for m in TABLE.findall(t.expected_sql or "")}


def reaches(
    setup: str,
    question: Question,
    groups: Sequence[str],
    lineage: Mapping[str, Sequence[str]] | None = None,
) -> bool | None:
    """Whether `setup` can reach `question`'s data: each table in its reach, or each of the table's
    `silver` sources (`lineage`); None when its reach is not declared here."""
    if setup in METRIC_REACH:
        return any(g in groups for g in METRIC_REACH[setup])
    reach = TABLE_REACH.get(setup)
    if reach is None:
        return None
    lineage = lineage or {}

    def one(schema: str, table: str) -> bool:
        if reach(schema, table):
            return True
        found = lineage.get(f"{schema}.{table}")
        return bool(found) and all(reach(*s.split(".", 1)) for s in found)

    return all(one(schema, table) for schema, table in tables(question))


def reach_limits(
    questions: Iterable[Question],
    groups: Mapping[str, Sequence[str]],
    lineage: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, list[str]]:
    """Per setup with a declared reach, the cases out of it (sorted; setups with none left out)."""
    questions = list(questions)
    out: dict[str, list[str]] = {}
    for setup in SETUPS:
        out[setup] = sorted(
            q.id for q in questions if reaches(setup, q, groups.get(q.id, []), lineage) is False
        )
    return {s: cases for s, cases in out.items() if cases}
