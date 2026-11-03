"""The `custom-toolbox` arm: an ADK agent whose only tools are MCP Toolbox's generated table-function tools (#330, Q5).

What it measures: whether an agent that can only call the seven tools in probes/330_tools.yaml (one per
`bet_shaped` table function, two ISO dates each) answers through them, does its own arithmetic over them, or
declines when no tool fits. One `McpToolset` over streamable HTTP to a local Toolbox; no tool of ours and no
cost guard: every statement is fixed (the agent only picks the dates), and the widest range each can take
dry-runs at 11.5 KB or less (the #330 finding).
The source uses `useClientOAuth`, so the agent's MCP client sends the caller's token in `Authorization` and
Toolbox calls BigQuery with it; stdio carries no header, so this arm needs Toolbox over HTTP.

Env: `BET_TOOLBOX_MCP` (default http://127.0.0.1:5000/mcp); `BET_MCP_TOKEN` (the caller's Google token; on a
cloud session the proxy injects Google's, so a placeholder; on a laptop `gcloud auth print-access-token`);
the model's (semantic_agent.model: OpenRouter's free tier).
Start Toolbox first, from the repo root (download and checksum as probes/330_toolbox_check.sh does):
  ~/.local/toolbox/toolbox-1.1.0 --config docs/research/semantic-bet/probes/330_tools.yaml --port 5000
Run from services/semantic-agent:
  uv run python ../../docs/research/semantic-bet/probes/330_toolbox_agent.py "<question>"
prints one JSON line: the question, every tool call with its arguments and result head, and the answer.
probes/328_mcp_live.py --agent 330_toolbox_agent.py runs it over frozen cases and scores them.
Live: yes (BigQuery on the lab project); run make gcp-cost-check and gcp-usage-check before and after.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from semantic_agent.bet_live import converse
from semantic_agent.model import (
    answer_model_failure,
    build_model,
    request_config,
)

TOOLBOX_MCP = os.environ.get("BET_TOOLBOX_MCP", "http://127.0.0.1:5000/mcp")
APP = "bet_custom_toolbox"

INSTRUCTION = """\
You answer business questions about an online shop's sales, returns and marketing.
Your only source of figures is your tools: each one returns the business's governed metrics for a range of
days (start_date and end_date, inclusive, as YYYY-MM-DD), one row per day or per group.
Pick the tool whose description fits the question, call it for the days the question names, and answer from
its rows; when the question needs a total over the days, add up the rows only where the figure is additive.
Every number you give must come from a tool result in this turn.
If no tool returns what the question asks for, say that you cannot answer it with the available metrics.
Answer in one or two sentences: the figure with its unit, and the days or period it covers.
"""


def _connection() -> StreamableHTTPConnectionParams:
    token = os.environ.get("BET_MCP_TOKEN", "proxy-injected")
    return StreamableHTTPConnectionParams(
        url=TOOLBOX_MCP, headers={"Authorization": f"Bearer {token}"}
    )


def build_agent() -> LlmAgent:
    return LlmAgent(
        name=APP,
        description="Answers business questions through generated MCP Toolbox tools over governed table functions.",
        model=build_model(),
        generate_content_config=request_config(),
        instruction=INSTRUCTION,
        tools=[McpToolset(connection_params=_connection())],
        on_model_error_callback=answer_model_failure,
    )


async def ask(question: str) -> dict[str, Any]:
    """One question in a fresh session: its tool calls, answer, reasoning and any model failure."""
    return (await converse(build_agent(), [question]))[0]


if __name__ == "__main__":
    print(json.dumps(asyncio.run(ask(" ".join(sys.argv[1:]))), default=str))
