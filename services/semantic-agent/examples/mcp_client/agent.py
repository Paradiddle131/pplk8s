"""Another team's agent that reaches the semantic layer only through MCP (semantic/PLAN.md SL-20).

Not deployed and not in the image: it shows an MCP-capable agent CLI (`adk run`) answering through
the MCP server (`make agent-mcp`), with no tool of its own and no MetricFlow, audited as the agent
its token names.

Env: `SEMANTIC_MCP_URL` (http://127.0.0.1:8765), `SEMANTIC_MCP_TOKEN`, and the model's own
(model.py: OpenRouter's free tier).
Run: `uv run adk run examples/mcp_client "<question>"` from services/semantic-agent.
"""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from semantic_agent.model import answer_model_failure, build_model, request_config

url = os.environ.get("SEMANTIC_MCP_URL", "http://127.0.0.1:8765")
connection = StreamableHTTPConnectionParams(
    url=f"{url}/mcp",
    headers={"Authorization": f"Bearer {os.environ.get('SEMANTIC_MCP_TOKEN', '')}"},
)

root_agent = LlmAgent(
    name="mcp_client",
    description="Answers business questions through the semantic layer's MCP server.",
    model=build_model(),
    generate_content_config=request_config(),
    instruction=(
        "Answer business questions only with figures the semantic layer's query_metrics tool "
        "returns in this turn; find the metric with list_metrics first. Answer in one sentence "
        "with the figure, its unit and its period, then quote freshness.statement word for word."
    ),
    tools=[McpToolset(connection_params=connection)],
    on_model_error_callback=answer_model_failure,
)
