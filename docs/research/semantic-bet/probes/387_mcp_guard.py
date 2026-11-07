"""`cc-native-mcp`'s one MCP server (#387, #388): Google's BigQuery and Knowledge Catalog MCP tools, filtered to
`native-mcp`'s 16 read-only names and behind the same cost guard, for a headless Claude Code run.

Why a local server: `native-mcp`'s guard is an ADK before-tool callback (probes/328_mcp_agent.py's `cost_guard`:
the project pinned, a dry run under BET_MAX_BYTES before every `execute_sql_readonly`, `execute_query`'s billed
cap); Claude Code has no such callback, so the same guard runs here, in front of Google's servers, and Claude Code
is given only this server (`--strict-mcp-config`). Tools are listed with Google's own names, descriptions and
input schemas, unchanged; a call outside the 16 is refused. Every call is appended to BET_GUARD_LOG (JSONL: when,
tool, arguments, whether it ran, the result's head), a server-side record the transcript audit can be held to.

Env: GCP_PROJECT, BET_BIGQUERY_MCP, BET_CATALOG_MCP, BET_MAX_BYTES, BET_MAX_BILLED, BET_SQL_DENY (as 328_mcp_agent.py);
BET_GUARD_PORT (8766), BET_GUARD_LOG. On cloud the egress proxy authenticates Google's endpoints; elsewhere set
BET_MCP_TOKEN. Run from services/semantic-agent:
  uv run python ../../docs/research/semantic-bet/probes/387_mcp_guard.py
The endpoint is http://127.0.0.1:8766/mcp. Live: make gcp-cost-check and gcp-usage-check before and after.
"""

from __future__ import annotations

import asyncio
import datetime
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

import httpx2
import mcp_types as types
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.lowlevel import Server

HERE = Path(__file__).resolve().parent
LOG = Path(os.environ.get("BET_GUARD_LOG", "/tmp/387_mcp_guard.jsonl"))
HEAD = 2000


def _probe():
    spec = importlib.util.spec_from_file_location(
        "bet_mcp_agent", HERE / "328_mcp_agent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


ARM = _probe()
UPSTREAMS = {ARM.BIGQUERY_MCP: ARM.BIGQUERY_TOOLS, ARM.CATALOG_MCP: ARM.CATALOG_TOOLS}
_tools: dict[str, tuple[str, types.Tool]] = {}
_lock: asyncio.Lock | None = None


def _client(url: str) -> Client:
    token = os.environ.get("BET_MCP_TOKEN", "proxy-injected")
    http = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=120)
    return Client(streamable_http_client(url, http_client=http))


async def tools() -> dict[str, tuple[str, types.Tool]]:
    """The declared tools each upstream lists, by name, with the upstream that serves it."""
    global _lock
    _lock = _lock or asyncio.Lock()
    async with _lock:  # concurrent first calls must never see a half-filled list
        if not _tools:
            found = {}
            for url, names in UPSTREAMS.items():
                async with _client(url) as client:
                    listed = await client.list_tools()
                # Google marks list_entries and get_glossary app-only (`_meta.ui.visibility: ["app"]`), which
                # Claude Code honours and ADK ignores: the native-mcp arm's model was offered both, so its mirror
                # lists them without that display hint (#387, 2026-11-06). Names, schemas, text: unchanged.
                found |= {
                    t.name: (url, t.model_copy(update={"meta": None}))
                    for t in listed.tools
                    if t.name in names
                }
            _tools.update(found)
    return _tools


def record(tool: str, args: dict[str, Any], ran: bool, result: Any) -> None:
    at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = json.dumps(result, default=str)[:HEAD]
    with LOG.open("a") as out:
        out.write(
            json.dumps(
                {"at": at, "tool": tool, "args": args, "ran": ran, "result": text}
            )
            + "\n"
        )


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(text=message)], is_error=True
    )


async def _call(url: str, name: str, args: dict[str, Any]) -> types.CallToolResult:
    async with _client(url) as client:
        return await client.call_tool(name, args)


def _dumped(result: types.CallToolResult) -> dict[str, Any]:
    dumped = result.model_dump(mode="json", by_alias=True)
    return {
        "structuredContent": dumped.get("structuredContent"),
        "content": dumped.get("content"),
    }


async def guard(name: str, args: dict[str, Any], url: str) -> str | None:
    """328_mcp_agent.cost_guard's checks, word for word in effect: a refusal's text, or None to run the call
    (with `args` pinned and capped in place)."""
    if name == "execute_query" and ARM.SQL_DENY:
        return "refused: execute_query is off in this configuration"
    if name == "execute_query":
        args["projectId"] = ARM.PROJECT
        bigquery = (
            args.get("bigquery") if isinstance(args.get("bigquery"), dict) else {}
        )
        args["bigquery"] = {**bigquery, "maximumBilledBytes": str(ARM.MAX_BILLED)}
        return None
    if name != "execute_sql_readonly":
        return None
    args["projectId"] = ARM.PROJECT
    if blocked := ARM.denied(str(args.get("query", ""))):
        return f"refused: the query reads dataset {blocked}, which is out of reach; use silver"
    if args.get("dryRun"):
        return None
    raw = _dumped(await _call(url, name, {**args, "dryRun": True}))
    dry = ARM._payload(raw)
    if dry.get("errors") or "totalBytesProcessed" not in dry:
        return f"the dry run refused the query: {ARM.dry_run_refusal(raw, dry)}"
    if int(dry["totalBytesProcessed"]) > ARM.MAX_BYTES:
        return f"refused: the query would process {dry['totalBytesProcessed']} bytes, over {ARM.MAX_BYTES}"
    return None


async def on_list_tools(ctx, params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=[tool for _, tool in (await tools()).values()])


async def on_call_tool(
    ctx, params: types.CallToolRequestParams
) -> types.CallToolResult:
    name, args = params.name, dict(params.arguments or {})
    served = (await tools()).get(name)
    if served is None:
        record(name, args, False, "refused: not one of native-mcp's tools")
        return _error(f"refused: {name} is not one of this setup's tools")
    url = served[0]
    if refusal := await guard(name, args, url):
        record(name, args, False, refusal)
        return _error(refusal)
    result = await _call(url, name, args)
    record(name, args, True, result.model_dump(mode="json", by_alias=True))
    return result


def main() -> None:
    import uvicorn

    server = Server(
        "native-mcp-guard",
        instructions="Google's BigQuery and Knowledge Catalog MCP tools, read-only, behind the bet's cost guard.",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )
    port = int(os.environ.get("BET_GUARD_PORT", "8766"))
    uvicorn.run(
        server.streamable_http_app(host="127.0.0.1"),
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
