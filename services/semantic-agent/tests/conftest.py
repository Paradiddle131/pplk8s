from __future__ import annotations

import asyncio
import datetime
import json
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import Field

FIXTURES = Path(__file__).parent / "fixtures"
# The catalog `make dbt-catalog` wrote for dbt/dev/fixture.sql (S2), so the tests need no dbt.
os.environ.setdefault("SEMANTIC_CATALOG", str(FIXTURES / "agent.json"))
# No test reaches a live model, so none spends the free tier's quota: a stray OpenRouter call goes
# to a closed local port instead (tests that need a provider answer start their own on localhost).
os.environ["OPENROUTER_API_BASE"] = "http://127.0.0.1:9/api/v1"


@pytest.fixture(autouse=True)
def no_ledger(monkeypatch):
    """query_metrics' freshness without a warehouse: every product has no ready interval."""
    from semantic_agent import tools
    from semantic_agent.freshness import assess

    now = datetime.datetime.now(datetime.UTC)
    monkeypatch.setattr(
        tools, "freshness", lambda products: assess([(p, None, None) for p in products], now)
    )


class ScriptedLlm(BaseLlm):
    """The agent loop without a live model: one scripted step per model turn, a step being a tool
    call `(name, args)` or the final answer text. Keeps every request it was sent."""

    model: str = "scripted"
    steps: list[tuple[str, dict[str, Any]] | str] = Field(default_factory=list)
    requests: list[LlmRequest] = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse]:
        self.requests.append(llm_request)
        step = self.steps[len(self.requests) - 1]
        if isinstance(step, str):
            part = types.Part(text=step)
        else:
            part = types.Part(function_call=types.FunctionCall(name=step[0], args=step[1]))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))

    def tool_results(self) -> list[dict[str, Any]]:
        """Every tool result the model was shown, in order."""
        last = self.requests[-1]
        return [
            {"name": p.function_response.name, "response": p.function_response.response}
            for content in last.contents
            for p in content.parts or []
            if p.function_response
        ]


def run_turn(agent: LlmAgent, question: str) -> list[Any]:
    """One user turn through ADK's own Runner; returns the events."""

    async def go() -> list[Any]:
        runner = Runner(app_name="test", agent=agent, session_service=InMemorySessionService())
        session = await runner.session_service.create_session(app_name="test", user_id="u")
        message = types.Content(role="user", parts=[types.Part(text=question)])
        return [
            event
            async for event in runner.run_async(
                user_id="u", session_id=session.id, new_message=message
            )
        ]

    return asyncio.run(go())


def final_text(events: list[Any]) -> str:
    return "".join(p.text or "" for e in events if e.is_final_response() for p in e.content.parts)


def service_unreachable(what: str, exc: Exception) -> None:
    """Skip on a laptop without `make services-up`; fail where the gate promised the services."""
    message = f"{what} not reachable (make services-up): {exc}"
    if os.environ.get("PPLK8S_REQUIRE_WAREHOUSE") == "1":
        pytest.fail(message)
    pytest.skip(message)


def catalog_json() -> dict[str, Any]:
    return json.loads((FIXTURES / "agent.json").read_text())
