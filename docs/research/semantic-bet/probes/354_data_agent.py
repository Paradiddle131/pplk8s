"""The data-agent arms as #352's runner asks them: a Conversational Analytics data agent, one conversation per run (#354, Q8).

What it measures: per turn, what the data agent did (its generated SQL and any matched verified query, as
`calls`) and its final answer, every turn of a frozen case in one stateless conversation: each `:chat` request
carries the conversation so far (the user's messages and every message the agent streamed back), as the API's
stateless multi-turn mode takes it. The agents are the ones each arm's probe built and published
(`bet-kc` by 327_kc_agent.py, `bet-shaped` by 329_shaped_agent.py, `bet-graph` by 331_graph_agent.py, `bet-kc-max` by
360_kc_max.py; `bet-context`
and `bet-governed` by `--copy` below), chatted as they stand, never republished here. Each chat is one request against the `--requests` budget; Google's model
answers, free until 2026-12-31, so no OpenRouter quota is spent.
A refused chat is a failure the runner leaves out of the log: HTTP 401 or 403 `auth` (ends the pass), anything
else asked again on a later pass; a failed connection (reset, timeout) is retried like a 429, then left the same way. A 429 is `rate_limit`, never `daily_quota`: the Chat API's quotas are per minute
(160 a project, no daily cap), and Google sheds load with 429 `Request throttled at the client by
AdaptiveThrottler`, so a throttled chat is retried after BACKOFF_S before it fails; each attempt is one request.

Run through the runner, live, after `make gcp-cost-check` and `make gcp-usage-check` (from services/semantic-agent):
  GCP_PROJECT=pplk8s-lab-001 DBT_DBNAME=dbt_dev uv run python ../../docs/research/semantic-bet/probes/328_mcp_live.py \
    --agent 354_data_agent.py --arm native-kc [--runs 3] [--requests 100] [--minutes 35] [case id...]
`--legacy <arm>...` (run from the repo root as `python3 -I`): republish each arm's agent with its published context
plus the `legacy` tables, which RULE.md puts in reach of every SQL arm; everything else in the context is kept.
`--copy <arm>...` (the same way): create or update `bet-context` from `pplk8s-semantic`'s published context (our
generated context, PR #310's publish.py) and `bet-governed` from `pplk8s-governed`'s, each with the legacy tables;
the source agents are only read.
Env: GCP_PROJECT (required); the credential as platform/gcp/data-agent/publish.py picks it (on cloud the proxy
injects it).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
# The model a data agent answers with: Google's, chosen by the service (`options.model: MODEL_UNSPECIFIED`), never
# the runner's MODEL_ID; logged as the rows' `model`, so the report never pairs these arms with an OpenRouter one.
MODEL = "google-data-agent (MODEL_UNSPECIFIED)"
# Each data-agent arm's agent, in RULE.md's rung order.
AGENTS = {
    "native-context": "bet-context",
    "native-governed": "bet-governed",
    "native-kc": "bet-kc",
    "native-shaped": "bet-shaped",
    "native-graph": "bet-graph",
    "native-kc-max": "bet-kc-max",  # 360_kc_max.py --publish
}


def _shaped():
    """329_shaped_agent.py: its chat transport, chat() and summarise()."""
    spec = importlib.util.spec_from_file_location(
        "bet_shaped_probe", HERE / "329_shaped_agent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def failure(status: int, payload: object) -> dict[str, Any] | None:
    """A refused chat in the runner's failure shape (semantic_agent.model.ModelFailure's fields)."""
    if status == 200:
        return None
    kind = {401: "auth", 403: "auth", 429: "rate_limit"}.get(status, "error")
    message = f"HTTP {status}: {json.dumps(payload, default=str)[:300]}"
    return {"kind": kind, "message": message, "retry_after_s": None}


def turn_of(question: str, summary: dict[str, Any]) -> dict[str, Any]:
    """One turn in the runner's shape, from 329_shaped_agent.summarise()'s reading of the stream."""
    calls = [
        {"tool": "generated_sql", "args": {"sql": sql}}
        for sql in summary["generated_sql"]
    ]
    calls += [
        {"tool": "matched_query", "args": {"query": q}}
        for q in summary["matched_query"]
    ]
    return {
        "question": question,
        "calls": calls,
        "answer": "\n".join(summary["final_response"]).strip(),
        "thought": "\n".join(t for t in summary["texts"] if t.startswith("THOUGHT")),
        "model_calls": 1,
    }


def asker(arm: str) -> Callable[[Sequence[str]], Awaitable[list[dict[str, Any]]]]:
    """The runner's `ask` for this arm: every question of a case in one stateless conversation."""
    agent_id = AGENTS.get(arm) or sys.exit(
        f"354_data_agent: no data agent for {arm}: {sorted(AGENTS)}"
    )
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    shaped = _shaped()
    shaped.AGENT_ID = agent_id  # chat() addresses the module's agent
    publish = shaped.load_publish()
    send = shaped.chat_transport(publish.access_token(dict(os.environ)), project)

    def conversation(questions: Sequence[str]) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        turns = []
        for question in questions:
            history.append({"userMessage": {"text": question}})
            status, stream, attempts = chat_throttled(
                lambda h=history: chat_with(shaped, send, project, h)[:2]
            )
            if failed := failure(status, stream):
                turns.append(
                    {
                        "question": question,
                        "calls": [],
                        "answer": "",
                        "model_calls": attempts,
                        "failure": failed,
                    }
                )
                break
            streamed = stream if isinstance(stream, list) else [stream]
            history += [
                m for m in streamed if isinstance(m, dict) and "systemMessage" in m
            ]
            turns.append(
                {**turn_of(question, shaped.summarise(stream)), "model_calls": attempts}
            )
        return turns

    async def ask(questions: Sequence[str]) -> list[dict[str, Any]]:
        import anyio  # the runner's venv has it; --legacy runs on the system Python

        return await anyio.to_thread.run_sync(conversation, questions)

    return ask


# Seconds to wait before each retry of a throttled (429) chat.
BACKOFF_S = (15, 30, 60)


def chat_throttled(
    chat: Callable[[], tuple[int, object]],
    backoff: Sequence[float] = BACKOFF_S,
    wait: Callable[[float], None] = time.sleep,
) -> tuple[int, object, int]:
    """chat() retried after each of `backoff`'s waits while it answers 429 or the connection fails
    (status 0: a reset or a timeout, #364, which ended a whole pass before): its last status and payload,
    and how many requests it sent. A chat is stateless, so asking it again is safe."""

    def attempt() -> tuple[int, object]:
        try:
            return chat()
        except OSError as error:  # ConnectionResetError, URLError, TimeoutError
            return 0, {"error": {"message": f"{type(error).__name__}: {error}"}}

    status, payload = attempt()
    attempts = 1
    for seconds in backoff:
        if status not in (0, 429):
            break
        wait(seconds)
        status, payload = attempt()
        attempts += 1
    return status, payload, attempts


def chat_with(
    shaped, send, project: str, messages: list[dict[str, Any]]
) -> tuple[int, object, float]:
    """329_shaped_agent.chat() with the conversation so far instead of one question."""
    parent = f"projects/{project}/locations/{shaped.LOCATION}"
    body = {
        "parent": parent,
        "messages": messages,
        "dataAgentContext": {"dataAgent": f"{parent}/dataAgents/{shaped.AGENT_ID}"},
    }
    started = time.monotonic()
    status, payload = send(
        "POST",
        f"https://geminidataanalytics.{shaped.LOCATION}.rep.googleapis.com/v1/{parent}:chat",
        body,
    )
    return status, payload, round(time.monotonic() - started, 1)


# RULE.md: every arm that writes SQL is given the `legacy` schema beside the trusted layers.
LEGACY = ["channel_daily", "country_sales", "daily_net_sales"]


def with_legacy(context: dict[str, Any], project: str) -> dict[str, Any]:
    """The context with the legacy tables added to its BigQuery table references (kept once)."""
    context = json.loads(json.dumps(context))
    refs = (
        context.setdefault("datasourceReferences", {})
        .setdefault("bq", {})
        .setdefault("tableReferences", [])
    )
    have = {(r.get("datasetId"), r.get("tableId")) for r in refs}
    refs += [
        {"projectId": project, "datasetId": "legacy", "tableId": t}
        for t in LEGACY
        if ("legacy", t) not in have
    ]
    return context


# The main track's agents whose published context `--copy` gives a bet arm (read, never written).
SOURCES = {
    "native-context": "pplk8s-semantic",
    "native-governed": "pplk8s-governed",
}


def published_tables(agent: dict[str, Any]) -> list[str]:
    """The `dataset.table` names an agent's published context references."""
    context = (agent.get("dataAnalyticsAgent") or {}).get("publishedContext") or {}
    refs = ((context.get("datasourceReferences") or {}).get("bq") or {}).get(
        "tableReferences"
    ) or []
    return [f"{r['datasetId']}.{r['tableId']}" for r in refs]


def copy_agent(arm: str) -> int:
    """Publish the arm's bet agent from its source agent's published context plus the legacy tables."""
    source = SOURCES.get(arm) or sys.exit(
        f"354_data_agent: --copy takes {sorted(SOURCES)}, not {arm}"
    )
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    shaped = _shaped()
    publish = shaped.load_publish()
    send = publish.http_transport(publish.access_token(dict(os.environ)), project)
    base = f"{publish.endpoint(shaped.LOCATION)}/v1/projects/{project}/locations/{shaped.LOCATION}/dataAgents"
    reader = publish.Publisher(send, project, shaped.LOCATION, source)
    current = reader.call("GET", f"{base}/{source}")
    published = (current.get("dataAnalyticsAgent") or {}).get("publishedContext") or {}
    if not published:
        print(f"354_data_agent: {source} has no published context")
        return 2
    agent = publish.desired(
        with_legacy(published, project),
        None,
        display_name=f"bet {arm}",
        description=f"The semantic bet's {arm} arm: {source}'s published context plus the legacy tables.",
    )
    publisher = publish.Publisher(send, project, shaped.LOCATION, AGENTS[arm])
    try:
        writes = publisher.publish(agent)
    except publish.PublishError as error:
        print(f"354_data_agent: {AGENTS[arm]} publish refused: {error}")
        return 2
    again = publisher.call("GET", f"{base}/{AGENTS[arm]}")
    print(
        f"354_data_agent: {AGENTS[arm]} from {source}: writes {writes}; "
        f"published tables {published_tables(again)}"
    )
    return 0


def give_legacy(arm: str) -> int:
    """Republish the arm's agent with its published context plus the legacy tables; everything else kept."""
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    shaped = _shaped()
    publish = shaped.load_publish()
    send = publish.http_transport(publish.access_token(dict(os.environ)), project)
    publisher = publish.Publisher(send, project, shaped.LOCATION, AGENTS[arm])
    current = publisher.call(
        "GET", f"{publish.endpoint(shaped.LOCATION)}/v1/{publisher.name}"
    )
    published = (current.get("dataAnalyticsAgent") or {}).get("publishedContext") or {}
    context = with_legacy(published, project)
    if context == published:
        print(f"354_data_agent: {AGENTS[arm]} already has the legacy tables")
        return 0
    agent = publish.desired(
        context,
        None,
        display_name=current["displayName"],
        description=current["description"],
    )
    try:
        writes = publisher.publish(agent)
    except publish.PublishError as error:
        print(f"354_data_agent: {AGENTS[arm]} publish refused: {error}")
        return 2
    again = publisher.call(
        "GET", f"{publish.endpoint(shaped.LOCATION)}/v1/{publisher.name}"
    )
    kept = (again.get("dataAnalyticsAgent") or {}).get("publishedContext") or {}
    tables = [
        f"{r['datasetId']}.{r['tableId']}"
        for r in ((kept.get("datasourceReferences") or {}).get("bq") or {}).get(
            "tableReferences"
        )
        or []
    ]
    print(f"354_data_agent: {AGENTS[arm]} writes {writes}; published tables {tables}")
    return 0


if __name__ == "__main__":
    # python3 -I 354_data_agent.py --legacy <arm>...: give each arm's agent the legacy tables (RULE.md);
    # --copy <arm>...: publish bet-context / bet-governed from the main track's agents.
    actions = {"--legacy": give_legacy, "--copy": copy_agent}
    if sys.argv[1:2] not in ([a] for a in actions) or not sys.argv[2:]:
        sys.exit("usage: 354_data_agent.py --legacy|--copy <arm>...")
    action = actions[sys.argv[1]]
    raise SystemExit(max(action(arm) for arm in sys.argv[2:]))
