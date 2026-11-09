"""The semantic layer's three tools over MCP, for agents outside ADK (semantic/PLAN.md SL-20).

Claude, Gemini CLI or a Vertex AI agent can then ask through metrics instead of writing SQL: the
server exposes `list_metrics`, `describe_metric` and `query_metrics` from tools.py, with their
argument checks, over streamable HTTP. A data call gets its audit row and its metrics' freshness
from guard.py's `guarded`, the code ADK's after-tool callback runs, so both surfaces audit alike.

Every client presents a bearer token, and the token names the agent its audit rows are written
as: one token per client is the lab's stand-in for a client's service account at work. A server
with no tokens refuses to start, since a call it could not attribute could not be audited.

Env: `SEMANTIC_MCP_CLIENTS`, comma-separated `<agent>=<token>` pairs; `SEMANTIC_MCP_HOST` and
`SEMANTIC_MCP_PORT` (127.0.0.1:8765); `SEMANTIC_MCP_URL`, the URL clients reach it at; the
metrics' own env (tools.py, audit.py, freshness.py).
Run: `python -m semantic_agent.mcp_server`; the endpoint is `<SEMANTIC_MCP_URL>/mcp`.
"""

from __future__ import annotations

import hmac
import inspect
import os
from collections.abc import Callable, Mapping
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic_core import to_jsonable_python

from semantic_agent import tools
from semantic_agent.audit import Caller
from semantic_agent.guard import guarded

SESSION_HEADER = "mcp-session-id"
INSTRUCTIONS = """\
The business's metrics, each with one definition. Call list_metrics first, describe_metric for a
metric's dimensions, and query_metrics for every figure; quote its freshness.statement.
"""


class ClientTokens:
    """The bearer tokens the server accepts, each naming the agent its calls are audited as."""

    def __init__(self, agents: Mapping[str, str]):
        self._agents = dict(agents)  # token -> agent

    @classmethod
    def parse(cls, spec: str) -> ClientTokens:
        """Tokens from `<agent>=<token>,...`; refuses an empty, malformed or repeated entry."""
        agents: dict[str, str] = {}
        for entry in filter(None, (part.strip() for part in spec.split(","))):
            agent, sep, token = entry.partition("=")
            if not sep or not agent.strip() or not token.strip():
                raise ValueError(f"SEMANTIC_MCP_CLIENTS entry {entry!r} is not <agent>=<token>")
            if token.strip() in agents:
                raise ValueError("SEMANTIC_MCP_CLIENTS gives two clients the same token")
            agents[token.strip()] = agent.strip()
        if not agents:
            raise ValueError("SEMANTIC_MCP_CLIENTS names no client, so no call could be audited")
        return cls(agents)

    async def verify_token(self, token: str) -> AccessToken | None:
        for known, agent in self._agents.items():
            if hmac.compare_digest(token.encode(), known.encode()):
                return AccessToken(token=token, client_id=agent, scopes=[])
        return None


def caller(ctx: Context) -> Caller:
    """The caller of an MCP tool call: the agent its token names, its MCP session and the
    request's id. The bearer middleware has already refused a call without a valid token."""
    token = get_access_token()
    if token is None:
        raise PermissionError("an MCP tool call without a client token cannot be audited")
    headers = ctx.headers or {}
    session = headers.get(SESSION_HEADER)
    return Caller(agent=token.client_id, session_id=session, call_id=ctx.request_id)


def served(tool: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """`tool` as an MCP tool: its name, docstring and arguments, plus the request's context; a data
    tool's result goes through `guarded` with the caller the context names."""
    signature = inspect.signature(tool, eval_str=True)

    def call(ctx: Context, **args: Any) -> dict[str, Any]:
        response = tool(**args)
        if tool.__name__ in tools.CATALOG_TOOLS:
            return response
        # The arguments as JSON, as an ADK agent sends them: MCP validates `filters` into Filter
        # models, which the audit row's jsonb cannot hold, so every filtered query failed its
        # audit write and was withheld as "Error executing tool" (#432).
        sent = {
            name: to_jsonable_python(value) for name, value in args.items() if value is not None
        }
        return guarded(tool.__name__, sent, response, caller(ctx), tools.catalog)

    context = inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context)
    call.__signature__ = signature.replace(parameters=[*signature.parameters.values(), context])
    call.__name__, call.__doc__ = tool.__name__, tool.__doc__
    return call


def build_server(clients: ClientTokens, url: str) -> MCPServer:
    """The MCP server over the three tools, accepting `clients`' tokens; `url` is where clients
    reach it."""
    server = MCPServer(
        name="semantic-layer",
        instructions=INSTRUCTIONS,
        token_verifier=clients,
        auth=AuthSettings(issuer_url=url, resource_server_url=None),
    )
    for tool in tools.TOOLS:
        server.add_tool(served(tool), structured_output=True)
    return server


def main() -> None:
    import uvicorn

    host = os.environ.get("SEMANTIC_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("SEMANTIC_MCP_PORT", "8765"))
    url = os.environ.get("SEMANTIC_MCP_URL", f"http://{host}:{port}")
    server = build_server(ClientTokens.parse(os.environ.get("SEMANTIC_MCP_CLIENTS", "")), url)
    # Bearer tokens, not cookies, authenticate a call, so a rebinding page holds no credential.
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    app = server.streamable_http_app(transport_security=security, host=host)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
