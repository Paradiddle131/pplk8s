"""The three tools over MCP: same checks, and every data call audited as its client, with its
freshness (a real streamable HTTP server on a local port; no model, no warehouse)."""

from __future__ import annotations

import asyncio
import inspect
import json
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from semantic_agent import mcp_server, tools

ROWS = {
    "columns": ["metric_time__day", "orders_total"],
    "rows": [{"metric_time__day": "2026-10-01", "orders_total": 3}],
    "row_count": 1,
    "sql": "SELECT compiled_by_metricflow",
}
QUERY = {"metrics": ["orders_total"], "group_by": ["metric_time__day"], "start_date": "2026-10-01"}
CLIENTS = "claude_code=token-a,gemini_cli=token-b"


@pytest.fixture
def metricflow(monkeypatch):
    def run(query, catalog):
        query.request(catalog)  # refuses a metric the catalog lacks, as MetricFlow's run does
        return ROWS

    monkeypatch.setattr(tools, "run", run)


@pytest.fixture
def url(metricflow) -> Iterator[str]:
    """The MCP endpoint of a server on a free local port, for this test only."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    server = mcp_server.build_server(mcp_server.ClientTokens.parse(CLIENTS), base)
    app = server.streamable_http_app(host="127.0.0.1")
    web = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=web.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not web.started:
        assert time.monotonic() < deadline, "the MCP server did not start"
        time.sleep(0.05)
    yield f"{base}/mcp"
    web.should_exit = True
    thread.join(timeout=10)


def session(url: str, token: str | None) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    http = httpx2.AsyncClient(headers=headers, timeout=30)
    return Client(streamable_http_client(url, http_client=http))


async def calls(url: str, token: str, *steps: tuple[str, dict[str, Any]]) -> list[Any]:
    async with session(url, token) as client:
        return [await client.call_tool(name, args) for name, args in steps]


def test_the_server_lists_the_three_tools_with_the_agents_arguments(url):
    async def listed():
        async with session(url, "token-a") as client:
            return (await client.list_tools()).tools

    served = {tool.name: tool for tool in asyncio.run(listed())}
    assert set(served) == {"list_metrics", "describe_metric", "query_metrics"}
    for tool in tools.TOOLS:
        properties = served[tool.__name__].input_schema.get("properties", {})
        assert set(properties) == set(inspect.signature(tool).parameters)
        assert served[tool.__name__].description == tool.__doc__


def test_a_metric_query_is_audited_as_the_client_its_token_names_with_its_freshness(url, audit):
    listed, query = asyncio.run(
        calls(url, "token-b", ("list_metrics", {}), ("query_metrics", QUERY))
    )
    assert not listed.is_error and not query.is_error
    assert "orders_total" in {m["name"] for m in listed.structured_content["metrics"]}
    result = query.structured_content
    assert result["rows"] == ROWS["rows"]
    assert result["freshness"]["statement"].startswith("Freshness unknown: sales.silver")
    (row,) = audit  # listing metrics reads only the catalog
    assert (row["agent"], row["tool"], row["arguments"]) == ("gemini_cli", "query_metrics", QUERY)
    assert row["call_id"]
    assert row["rows_returned"] == 1
    assert row["freshness"] == result["freshness"]["statement"]


def test_a_refused_query_comes_back_as_an_error_and_is_audited(url, audit):
    (query,) = asyncio.run(
        calls(url, "token-a", ("query_metrics", {"metrics": ["average_basket_eur"]}))
    )
    assert "no metric named 'average_basket_eur'" in query.structured_content["error"]
    (row,) = audit
    assert row["agent"] == "claude_code"
    assert "no metric named 'average_basket_eur'" in row["error"]


def test_an_unwritable_audit_withholds_the_rows(url, monkeypatch):
    from semantic_agent import audit
    from semantic_agent.warehouse import WarehouseError

    def refuse(row):
        raise WarehouseError("connection refused")

    monkeypatch.setattr(audit, "record", refuse)
    (query,) = asyncio.run(calls(url, "token-a", ("query_metrics", QUERY)))
    assert "rows" not in query.structured_content
    assert "audit row could not be written" in query.structured_content["error"]


def test_an_adk_agent_outside_the_service_asks_through_mcp_with_its_own_token(url, audit):
    from google.adk.agents import LlmAgent
    from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

    from tests.conftest import ScriptedLlm, final_text, run_turn

    model = ScriptedLlm(steps=[("query_metrics", QUERY), "3 orders on 2026-10-01."])
    bearer = {"Authorization": "Bearer token-a"}
    connection = StreamableHTTPConnectionParams(url=url, headers=bearer)
    toolset = McpToolset(connection_params=connection)
    client = LlmAgent(name="another_team", model=model, tools=[toolset])
    events = run_turn(client, "How many orders on 1 October?")
    assert final_text(events) == "3 orders on 2026-10-01."
    (shown,) = model.tool_results()
    assert "Freshness unknown: sales.silver" in json.dumps(shown["response"])
    (row,) = audit
    assert (row["agent"], row["tool"], row["rows_returned"]) == ("claude_code", "query_metrics", 1)


@pytest.mark.parametrize("token", [None, "token-c"])
def test_a_client_without_a_known_token_is_refused(url, audit, token):
    headers = {"Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call"}
    call["params"] = {"name": "query_metrics", "arguments": QUERY}
    refused = httpx2.post(url, json=call, headers=headers, timeout=10)
    assert refused.status_code == 401
    assert audit == []


@pytest.mark.parametrize(
    ("spec", "problem"),
    [
        ("", "names no client"),
        ("claude_code", "is not <agent>=<token>"),
        ("a=t,b=t", "the same token"),
    ],
)
def test_the_client_list_must_name_every_client_once(spec, problem):
    with pytest.raises(ValueError, match=problem):
        mcp_server.ClientTokens.parse(spec)
