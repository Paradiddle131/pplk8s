"""The `native-mcp` arm: an ADK agent whose only tools are Google's managed MCP servers (#328, #346, Q3).

What it measures: whether an agent with nothing but BigQuery's and Knowledge Catalog's remote MCP tools
answers through the metric definitions Knowledge Catalog holds (after the dbt import, #326) or writes its own
SQL from technical metadata. No tool of ours: two `McpToolset`s over streamable HTTP, filtered to the
read-only tools; the one piece of our code is a before-tool guard, because BigQuery's `execute_sql_readonly`
takes no `maximumBytesBilled` (its input schema, read 2026-11-03): the guard pins `projectId` to the lab
project and dry-runs every query through the same tool, refusing one that would process more than
`BET_MAX_BYTES` (10 MiB) or that the dry run rejects.
With `BET_SQL_DENY` set (#350: `governed,gold,exposed,legacy,bet_*`), the guard also refuses any query that
names one of those datasets, and `execute_query` outright, so only the catalog's definitions and `silver`
are left to answer from; the agent still sees the datasets in listings and the catalog.

Env: `GCP_PROJECT` (the lab project); `BET_BIGQUERY_MCP` and `BET_CATALOG_MCP` (Google's endpoints by
default, the stand-in's for the offline check); `BET_MCP_TOKEN` (a bearer token; on a cloud session the
proxy injects Google's, so a placeholder; on a laptop `gcloud auth print-access-token`); `BET_MAX_BYTES`;
the model's (semantic_agent.model: OpenRouter's free tier).
Run from services/semantic-agent:
  uv run python ../../docs/research/semantic-bet/probes/328_mcp_agent.py "<question>"
prints one JSON line: the question, every tool call with its arguments and result head, and the answer.
Live against Google's endpoints (make gcp-cost-check and gcp-usage-check before and after); offline against
probes/328_mcp_standin.py (probes/328_standin_check.sh).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from semantic_agent.bet_live import converse
from semantic_agent.model import (
    answer_model_failure,
    build_model,
    request_config,
)

PROJECT = os.environ.get("GCP_PROJECT", "pplk8s-lab-001")
BIGQUERY_MCP = os.environ.get("BET_BIGQUERY_MCP", "https://bigquery.googleapis.com/mcp")
CATALOG_MCP = os.environ.get("BET_CATALOG_MCP", "https://dataplex.googleapis.com/mcp")
MAX_BYTES = int(os.environ.get("BET_MAX_BYTES", str(10 * 1024 * 1024)))
# execute_query's own cap is on bytes billed, which BigQuery rounds up to 10 MB per table read.
MAX_BILLED = int(os.environ.get("BET_MAX_BILLED", str(100 * 1024 * 1024)))
# Datasets the agent's SQL may not name (#350), comma-separated; a trailing * matches a prefix.
SQL_DENY = [
    d.strip() for d in os.environ.get("BET_SQL_DENY", "").split(",") if d.strip()
]


def denied(sql: str) -> str | None:
    """The first denied dataset the query names as `<dataset>.` (bare, project-qualified or backticked)."""
    for name in SQL_DENY:
        pattern = re.escape(name.rstrip("*")) + (r"\w*" if name.endswith("*") else "")
        if re.search(rf"(?<![\w-])`?(?:{pattern})`?\s*\.", sql, re.IGNORECASE):
            return name
    return None


# Every read-only tool the two servers list (tools/list, 2026-11-03: 9 on BigQuery's, 17 on Knowledge
# Catalog's); left out: execute_sql (DML and DDL), cancel_job, and the catalog's writes (create, update,
# upsert, delete, set_entry_group_iam_policy). execute_query runs a BigQuery job, capped by the guard.
BIGQUERY_TOOLS = [
    "list_dataset_ids",
    "list_table_ids",
    "get_dataset_info",
    "get_table_info",
    "execute_sql_readonly",
    "get_job",
    "get_query_results",
]
CATALOG_TOOLS = [
    "search_entries",
    "lookup_context",
    "lookup_entry",
    "lookup_entry_links",
    "list_entries",
    "get_glossary",
    "get_operation",
    "compile_query",
    "execute_query",
]

INSTRUCTION = f"""\
You answer business questions about the data in BigQuery project {PROJECT}.
First find the relevant assets with search_entries and read their context with lookup_context
(location "us"): it may hold the business's metric definitions; when it defines the metric asked for, follow
that definition exactly. Then read the figures with execute_sql_readonly (GoogleSQL, projectId {PROJECT}).
Every number you give must come from a query result in this turn. If the data cannot answer, say so.
Answer in one or two sentences: the figure with its unit, and the days or period it covers.
"""


def _payload(result: Any) -> dict[str, Any]:
    """The tool result as a dict: MCP's structured content, else its first text block parsed as JSON."""
    if not isinstance(result, dict):
        return {}
    if isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"]
    for block in result.get("content") or []:
        text = block.get("text") if isinstance(block, dict) else None
        if text:
            try:
                parsed = json.loads(text)
            except ValueError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
    return {}


def dry_run_refusal(result: Any, payload: dict[str, Any]) -> str:
    """Why a dry run refused a query, for the agent: BigQuery's own error text (#392).

    Google's server answers a failed dry run with `isError` and plain text (`Unrecognized name: description
    at [1:32]`), which `_payload` cannot parse; quote that text, else the parsed payload, cut at 500 characters.
    """
    if payload:
        return json.dumps(payload)[:500]
    texts = [
        block.get("text")
        for block in (result.get("content") or [] if isinstance(result, dict) else [])
        if isinstance(block, dict) and block.get("text")
    ]
    return (" ".join(texts) or "no reason given")[:500]


async def cost_guard(
    tool: BaseTool, args: dict[str, Any], tool_context: Any
) -> dict[str, Any] | None:
    """Pins every query to the lab project and lets it run only if a dry run passes under the cap;
    `execute_query`, which takes the cap itself, gets it set."""
    if tool.name == "execute_query" and SQL_DENY:
        return {"error": "refused: execute_query is off in this configuration"}
    if tool.name == "execute_query":
        args["projectId"] = PROJECT
        bigquery = (
            args.get("bigquery") if isinstance(args.get("bigquery"), dict) else {}
        )
        args["bigquery"] = {**bigquery, "maximumBilledBytes": str(MAX_BILLED)}
        return None
    if tool.name != "execute_sql_readonly":
        return None
    args["projectId"] = PROJECT
    blocked = denied(str(args.get("query", "")))
    if blocked:
        return {
            "error": f"refused: the query reads dataset {blocked}, which is out of reach; use silver"
        }
    if args.get("dryRun"):
        return None
    raw = await tool.run_async(args={**args, "dryRun": True}, tool_context=tool_context)
    dry = _payload(raw)
    if dry.get("errors") or "totalBytesProcessed" not in dry:
        return {"error": f"the dry run refused the query: {dry_run_refusal(raw, dry)}"}
    if int(dry["totalBytesProcessed"]) > MAX_BYTES:
        return {
            "error": f"refused: the query would process {dry['totalBytesProcessed']} bytes, over {MAX_BYTES}"
        }
    return None


def _connection(url: str) -> StreamableHTTPConnectionParams:
    token = os.environ.get("BET_MCP_TOKEN", "proxy-injected")
    return StreamableHTTPConnectionParams(
        url=url, headers={"Authorization": f"Bearer {token}"}
    )


def build_agent() -> LlmAgent:
    return LlmAgent(
        name="bet_native_mcp",
        description="Answers business questions through Google's BigQuery and Knowledge Catalog MCP servers.",
        model=build_model(),
        generate_content_config=request_config(),
        instruction=INSTRUCTION,
        tools=[
            McpToolset(
                connection_params=_connection(BIGQUERY_MCP), tool_filter=BIGQUERY_TOOLS
            ),
            McpToolset(
                connection_params=_connection(CATALOG_MCP), tool_filter=CATALOG_TOOLS
            ),
        ],
        before_tool_callback=cost_guard,
        on_model_error_callback=answer_model_failure,
    )


async def ask(question: str) -> dict[str, Any]:
    """One question in a fresh session: its tool calls, answer, reasoning and any model failure."""
    return (await converse(build_agent(), [question]))[0]


if __name__ == "__main__":
    print(json.dumps(asyncio.run(ask(" ".join(sys.argv[1:]))), default=str))
