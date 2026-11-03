"""The `native-mcp` arm: an ADK agent whose only tools are Google's managed MCP servers (#328, #346, Q3).

What it measures: whether an agent with nothing but BigQuery's and Knowledge Catalog's remote MCP tools
answers through the metric definitions Knowledge Catalog holds (after the dbt import, #326) or writes its own
SQL from technical metadata. No tool of ours: two `McpToolset`s over streamable HTTP, filtered to the
read-only tools; the one piece of our code is a before-tool guard, because BigQuery's `execute_sql_readonly`
takes no `maximumBytesBilled` (its input schema, read 2026-11-03): the guard pins `projectId` to the lab
project and dry-runs every query through the same tool, refusing one that would process more than
`BET_MAX_BYTES` (10 MiB) or that the dry run rejects.

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
import sys
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from google.genai import types
from semantic_agent.model import answer_model_failure, build_model, request_config

PROJECT = os.environ.get("GCP_PROJECT", "pplk8s-lab-001")
BIGQUERY_MCP = os.environ.get("BET_BIGQUERY_MCP", "https://bigquery.googleapis.com/mcp")
CATALOG_MCP = os.environ.get("BET_CATALOG_MCP", "https://dataplex.googleapis.com/mcp")
MAX_BYTES = int(os.environ.get("BET_MAX_BYTES", str(10 * 1024 * 1024)))
# The read-only tools Google's docs list (2026-11-03); execute_sql, which runs DML and DDL, is left out.
BIGQUERY_TOOLS = [
    "list_dataset_ids",
    "list_table_ids",
    "get_dataset_info",
    "get_table_info",
    "execute_sql_readonly",
]
CATALOG_TOOLS = ["search_entries", "lookup_context", "lookup_entry"]

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


async def cost_guard(
    tool: BaseTool, args: dict[str, Any], tool_context: Any
) -> dict[str, Any] | None:
    """Pins every query to the lab project and lets it run only if a dry run passes under the cap."""
    if tool.name != "execute_sql_readonly":
        return None
    args["projectId"] = PROJECT
    if args.get("dryRun"):
        return None
    dry = _payload(
        await tool.run_async(args={**args, "dryRun": True}, tool_context=tool_context)
    )
    if dry.get("errors") or "totalBytesProcessed" not in dry:
        return {"error": f"the dry run refused the query: {json.dumps(dry)[:500]}"}
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
    runner = InMemoryRunner(agent=build_agent(), app_name="bet_native_mcp")
    session = await runner.session_service.create_session(
        app_name="bet_native_mcp", user_id="bet"
    )
    calls: dict[
        str, dict[str, Any]
    ] = {}  # by function-call id: parallel calls answer out of order
    answer = ""
    message = types.Content(role="user", parts=[types.Part(text=question)])
    async for event in runner.run_async(
        user_id="bet", session_id=session.id, new_message=message
    ):
        for part in (event.content.parts if event.content else None) or []:
            if part.function_call:
                calls[part.function_call.id or str(len(calls))] = {
                    "tool": part.function_call.name,
                    "args": dict(part.function_call.args or {}),
                }
            elif part.function_response and part.function_response.id in calls:
                calls[part.function_response.id]["result"] = json.dumps(
                    part.function_response.response, default=str
                )[:400]
            elif part.text and event.is_final_response():
                answer += part.text
    await runner.close()
    return {
        "question": question,
        "calls": list(calls.values()),
        "answer": answer.strip(),
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(ask(" ".join(sys.argv[1:]))), default=str))
