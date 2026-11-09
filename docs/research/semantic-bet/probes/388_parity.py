"""What each data-agent setup is given and what its agent loop does, read from Google, not assumed (#388).

Two read-only halves, run from the repo root as `python3 -I` (the credential as publish.py picks it; on cloud the
proxy injects it), with `make gcp-cost-check` and `make gcp-usage-check` before and after:

  python3 -I docs/research/semantic-bet/probes/388_parity.py --agents
      GETs every bet data agent (354_data_agent.AGENTS) and prints one JSON line each: the tables its published
      context references, its verified queries, glossary terms and system instruction size, and its `options`
      (Python analysis on or off). Nothing is written to Google.
  python3 -I docs/research/semantic-bet/probes/388_parity.py --sample OUT.jsonl ARM:CASE...
      asks each case's first question once, in a fresh stateless chat (as 354_data_agent.py does, unlogged and
      unscored), and appends the raw stream plus a census of its system-message kinds (text by textType, schema,
      data by field, analysis, chart, error, exampleQueries) to OUT.jsonl: every step Google's loop took.
      The cases come from the bet's sets (semantic_bet*.yaml); a chat is free until 2026-12-31 and its queries
      are the agent's own, capped by the agent's published context as in every pass.

  uv run --project services/semantic-agent python docs/research/semantic-bet/probes/388_parity.py --grants
      checks the reach policy (RULE.md § The arms, 2026-11-09, #445) on the fixture: `agent_sql` (baseline and the
      hybrid's fallback) reads every `silver` table `agent_metrics` reads and `semantic.time_spine`, never a personal
      column, and `native-mcp` runs with `BET_SQL_DENY` unset; prints one JSON line, exit 1 on any mismatch.

The census names a step by the API's own fields (the v1 `Message` reference, read 2026-11-06):
https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/reference/rest/v1/Message
"""

from __future__ import annotations

import collections
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SET_FILES = ("semantic_bet.yaml", "semantic_bet_hard.yaml", "semantic_bet_hard_v2.yaml")


def _module(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def census(stream: object) -> dict[str, int]:
    """How many messages of each kind the chat streamed: `text:<textType>`, `schema:<query|result>`,
    `data:<field>`, `analysis:<field>`, `chart:<query|result>`, `error`, `exampleQueries`."""
    counts: collections.Counter[str] = collections.Counter()
    for message in stream if isinstance(stream, list) else [stream]:
        system = (message or {}).get("systemMessage") or {}
        for kind, body in system.items():
            if kind in ("groupId", "citation"):
                continue
            if kind == "text":
                counts[f"text:{(body or {}).get('textType', '?')}"] += 1
            elif kind == "analysis":
                event = (body or {}).get("progressEvent") or {}
                for field in event or (body or {}):
                    counts[f"analysis:{field}"] += 1
            elif isinstance(body, dict) and kind in ("schema", "data", "chart"):
                for field in body:
                    counts[f"{kind}:{field}"] += 1
            else:
                counts[kind] += 1
    return dict(sorted(counts.items()))


def agents() -> int:
    data_agent = _module("bet_data_agent", "354_data_agent.py")
    shaped = data_agent._shaped()
    publish = shaped.load_publish()
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    send = publish.http_transport(publish.access_token(dict(os.environ)), project)
    base = f"{publish.endpoint(shaped.LOCATION)}/v1/projects/{project}/locations/{shaped.LOCATION}/dataAgents"
    for arm, agent_id in data_agent.AGENTS.items():
        reader = publish.Publisher(send, project, shaped.LOCATION, agent_id)
        agent = reader.call("GET", f"{base}/{agent_id}")
        context = (agent.get("dataAnalyticsAgent") or {}).get("publishedContext") or {}
        print(
            json.dumps(
                {
                    "arm": arm,
                    "agent": agent_id,
                    "tables": data_agent.published_tables(agent),
                    "verified_queries": len(context.get("exampleQueries") or []),
                    "glossary_terms": len(context.get("glossaryTerms") or []),
                    "system_instruction_chars": len(
                        context.get("systemInstruction") or ""
                    ),
                    "options": context.get("options") or {},
                    "context_keys": sorted(context),
                    "update_time": agent.get("updateTime"),
                }
            )
        )
    return 0


def first_question(case: str) -> str:
    import yaml  # the semantic agent's environment has it; --sample runs there

    for name in SET_FILES:
        data = yaml.safe_load(
            (ROOT / "services/semantic-agent/evals" / name).read_text()
        )
        for q in data["questions"]:
            if q["id"] == case:
                return (q.get("turns") or [q])[0]["question"]
    raise SystemExit(f"388_parity: no case {case}")


def sample(out: Path, pairs: list[str]) -> int:
    data_agent = _module("bet_data_agent", "354_data_agent.py")
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    for pair in pairs:
        arm, _, case = pair.partition(":")
        shaped = data_agent._shaped()
        shaped.AGENT_ID = data_agent.AGENTS[arm]
        publish = shaped.load_publish()
        send = shaped.chat_transport(publish.access_token(dict(os.environ)), project)
        question = first_question(case)
        status, stream, seconds = data_agent.chat_with(
            shaped, send, project, [{"userMessage": {"text": question}}]
        )
        row: dict[str, Any] = {
            "arm": arm,
            "agent": shaped.AGENT_ID,
            "model": data_agent.MODEL,
            "case": case,
            "question": question,
            "status": status,
            "seconds": seconds,
            "census": census(stream),
            "summary": {
                k: v for k, v in shaped.summarise(stream).items() if k != "texts"
            },
            "stream": stream,
        }
        with out.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(
            json.dumps(
                {k: row[k] for k in ("arm", "case", "status", "seconds", "census")}
            )
        )
    return 0


# The reach policy (#445): what agent_sql must read in the fixture's database, as agent_metrics does.
POLICY_SCHEMAS = ("silver",)
POLICY_TABLES = ("semantic.time_spine",)


def _readable(conn: Any, role: str) -> dict[str, set[str]]:
    """Each table of the policy's schemas a role may SELECT from, with the columns it may read."""
    rows = conn.execute(
        "select table_schema || '.' || table_name, column_name from information_schema.column_privileges "
        "where grantee = %s and privilege_type = 'SELECT' and (table_schema = any(%s) "
        "or table_schema || '.' || table_name = any(%s))",
        [role, list(POLICY_SCHEMAS), list(POLICY_TABLES)],
    ).fetchall()
    out: dict[str, set[str]] = collections.defaultdict(set)
    for table, column in rows:
        out[table].add(column)
    return out


def grants() -> int:
    import psycopg  # the semantic agent's environment has it

    database = os.environ.get("DBT_DBNAME", "dbt_dev")
    url = os.environ.get(
        "WAREHOUSE_OWNER_URL",
        f"postgresql://warehouse:warehouse@localhost:5433/{database}",
    )
    with psycopg.connect(url) as conn:
        metrics = _readable(conn, "agent_metrics")
        sql = _readable(conn, "agent_sql")
        pii = {
            f"{s}.{t}.{c}"
            for s, t, c in conn.execute(
                "select n.nspname, c.relname, a.attname from pg_attribute a join pg_class c on c.oid = a.attrelid "
                "join pg_namespace n on n.oid = c.relnamespace where n.nspname = any(%s) and a.attnum > 0 "
                "and not a.attisdropped and not has_column_privilege('agent_metrics', c.oid, a.attnum, 'SELECT') "
                "and c.relkind in ('r', 'v', 'm')",
                [list(POLICY_SCHEMAS)],
            ).fetchall()
        }
    problems = []
    for table, columns in sorted(metrics.items()):
        if table.split(".")[0] in POLICY_SCHEMAS and not columns <= sql.get(
            table, set()
        ):
            problems.append(
                f"agent_sql misses {table}: {sorted(columns - sql.get(table, set()))}"
            )
    for table in POLICY_TABLES:
        if not sql.get(table):
            problems.append(f"agent_sql cannot read {table}")
    leaked = sorted(
        f"{t}.{c}" for t, cols in sql.items() for c in cols if f"{t}.{c}" in pii
    )
    if leaked:
        problems.append(f"agent_sql reads personal columns: {leaked}")
    deny = os.environ.get("BET_SQL_DENY", "")
    if deny:
        problems.append(
            f"BET_SQL_DENY is set ({deny}): native-mcp's reach would not be the policy's"
        )
    print(
        json.dumps(
            {
                "database": database,
                "agent_sql_tables": len(sql),
                "agent_metrics_silver_tables": sum(
                    t.startswith("silver.") for t in metrics
                ),
                "personal_columns_refused": len(pii),
                "problems": problems,
            }
        )
    )
    return 1 if problems else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--agents"]:
        raise SystemExit(agents())
    if args == ["--grants"]:
        raise SystemExit(grants())
    if args[:1] == ["--sample"] and len(args) >= 3:
        raise SystemExit(sample(Path(args[1]), args[2:]))
    sys.exit(
        "usage: 388_parity.py --agents | --grants | --sample OUT.jsonl ARM:CASE..."
    )
