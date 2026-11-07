"""A local stand-in for Google's BigQuery and Knowledge Catalog MCP servers, over the Compose warehouse.

What it is for (#346, Q3): testing probes/328_mcp_agent.py offline. It serves the read-only tool names and
the argument names Google's docs give (read 2026-11-03: BigQuery's `execute_sql_readonly`,
`list_dataset_ids`, `list_table_ids`, `get_table_info`; Knowledge Catalog's `search_entries`,
`lookup_context`), so the agent's discovery, tool filter, cost guard and one answer run with no Google
call. It is not a model of what those servers return: SQL runs on PostgreSQL as the baseline's read-only
`agent_sql` role (sql_baseline.agent.execute_sql), and `lookup_context` returns the dbt catalog's
technical metadata (tables, columns, descriptions), what Knowledge Catalog holds before the dbt import.
`STANDIN_DRY_BYTES` is the `totalBytesProcessed` every dry run reports (default 0), to drive the guard.

Env: the baseline's (`WAREHOUSE_SQL_URL`, `DBT_DBNAME`), the catalog's (`SEMANTIC_CATALOG`); `STANDIN_PORT`
(8766). Offline. Run from services/semantic-agent (needs `make services-up` and the agents' fixture,
tests/e2e/agent-fixture.sh):
  DBT_DBNAME=dbt_dev uv run python ../../docs/research/semantic-bet/probes/328_mcp_standin.py
Endpoints: http://127.0.0.1:<port>/bigquery/mcp and http://127.0.0.1:<port>/catalog/mcp.
"""

from __future__ import annotations

import contextlib
import os
import re
from typing import Any

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from semantic_agent.tools import catalog
from sql_baseline.agent import execute_sql
from starlette.applications import Starlette
from starlette.routing import Mount


def _models() -> list[dict[str, Any]]:
    return catalog().models


def _table(model: dict[str, Any]) -> tuple[str, str]:
    dataset, table = model["relation"].split(".")[-2:]
    return dataset.strip('"'), table.strip('"')


ENTRY = re.compile(
    r"projects/[^/]+/locations/[^/]+/entryGroups/[^/]+/entries/.*/datasets/([^/]+)/tables/([^/]+)"
)

bigquery = MCPServer(
    name="bigquery-standin",
    instructions="BigQuery's read-only tools, a local stand-in.",
)
knowledge = MCPServer(
    name="knowledge-catalog-standin",
    instructions="Knowledge Catalog, a local stand-in.",
)


@bigquery.tool()
def list_dataset_ids(projectId: str) -> dict[str, Any]:
    """Lists the datasets of a project."""
    return {"datasets": sorted({_table(m)[0] for m in _models()})}


@bigquery.tool()
def list_table_ids(projectId: str, datasetId: str) -> dict[str, Any]:
    """Lists the tables of a dataset."""
    return {"tables": sorted(t for d, t in map(_table, _models()) if d == datasetId)}


@bigquery.tool()
def get_table_info(projectId: str, datasetId: str, tableId: str) -> dict[str, Any]:
    """Gets a table's schema and description."""
    for model in _models():
        if _table(model) == (datasetId, tableId):
            columns = model.get("columns", [])
            fields = [
                {"name": c.get("name"), "description": c.get("description", "")}
                for c in columns
            ]
            return {
                "description": model.get("description", ""),
                "schema": {"fields": fields},
            }
    return {"error": f"Not found: Table {projectId}:{datasetId}.{tableId}"}


@bigquery.tool()
def execute_sql_readonly(
    projectId: str, query: str, dryRun: bool = False, timeoutMs: int = 20000
) -> dict[str, Any]:
    """Runs a read-only GoogleSQL query (a SELECT) and returns its rows; dryRun only validates it."""
    if dryRun:
        return {
            "totalBytesProcessed": os.environ.get("STANDIN_DRY_BYTES", "0"),
            "jobComplete": True,
        }
    # GoogleSQL's quoting and project-qualified names, made PostgreSQL's: backticks dropped, and
    # `<project>.<dataset>.<table>` read as `<dataset>.<table>`.
    result = execute_sql(query.replace("`", "").replace(f"{projectId}.", ""))
    if "error" in result:
        return {
            "errors": [{"reason": "invalidQuery", "message": result["error"]}],
            "jobComplete": True,
        }
    fields = [{"name": c} for c in result["columns"]]
    return {"schema": {"fields": fields}, "rows": result["rows"], "jobComplete": True}


@knowledge.tool()
def search_entries(projectId: str, query: str, pageSize: int = 10) -> dict[str, Any]:
    """Searches Knowledge Catalog for data assets matching a query; returns entry names."""
    words = [w.lower() for w in query.replace(":", " ").split() if w.isalnum()]
    results = []
    for model in _models():
        dataset, table = _table(model)
        text = f"{dataset} {table} {model.get('description', '')}".lower()
        if not words or any(w in text for w in words):
            name = (
                f"projects/{projectId}/locations/us/entryGroups/@bigquery/entries/"
                f"bigquery.googleapis.com/projects/{projectId}/datasets/{dataset}/tables/{table}"
            )
            results.append(
                {
                    "dataplexEntry": {
                        "name": name,
                        "fullyQualifiedName": f"bigquery:{projectId}.{dataset}.{table}",
                    }
                }
            )
    return {"results": results[: pageSize if pageSize > 0 else 10]}


@knowledge.tool()
def lookup_context(
    projectId: str, location: str, resources: list[str]
) -> dict[str, Any]:
    """Looks up LLM-ready metadata context (schema, descriptions) for up to 10 entries."""
    lines = []
    for resource in resources[:10]:
        # Entry names only, as the docs ask (projects/.../entryGroups/.../entries/<entry id>); the real
        # server's answer to another form is not known here, so the stand-in names the problem.
        found = ENTRY.fullmatch(resource)
        if not found:
            return {
                "error": f"INVALID_ARGUMENT: {resource!r} is not an entry name ({ENTRY.pattern})"
            }
        dataset, table = found.group(1), found.group(2)
        for model in _models():
            if _table(model) == (dataset, table):
                lines.append(
                    f"- table: {projectId}.{dataset}.{table}\n  description: {model.get('description', '')}"
                )
                lines.append("  columns:")
                for column in model.get("columns", []):
                    lines.append(
                        f"  - {column.get('name')}: {column.get('description', '')}"
                    )
    return {"context": "\n".join(lines) or "no context for these resources"}


def app() -> Starlette:
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    apps = {
        "bigquery": bigquery.streamable_http_app(
            transport_security=security, streamable_http_path="/mcp"
        ),
        "catalog": knowledge.streamable_http_app(
            transport_security=security, streamable_http_path="/mcp"
        ),
    }

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette):
        async with contextlib.AsyncExitStack() as stack:
            for sub in apps.values():
                await stack.enter_async_context(sub.router.lifespan_context(sub))
            yield

    return Starlette(
        routes=[Mount(f"/{k}", app=v) for k, v in apps.items()], lifespan=lifespan
    )


if __name__ == "__main__":
    uvicorn.run(
        app(),
        host="127.0.0.1",
        port=int(os.environ.get("STANDIN_PORT", "8766")),
        log_level="warning",
    )
