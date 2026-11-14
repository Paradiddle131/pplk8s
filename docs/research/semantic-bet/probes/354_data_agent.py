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
else asked again on a later pass; a failed connection (reset, timeout) is retried like a 429, then left the same way;
an answer that is the project's daily BigQuery query quota refusing the agent's query (QUOTA_ANSWER) is `daily_quota`
and ends the pass, so a spent quota is never scored as the arm's answer. A 429 is `rate_limit`, never `daily_quota`: the Chat API's quotas are per minute
(160 a project, no daily cap), and Google sheds load with 429 `Request throttled at the client by
AdaptiveThrottler`, so a throttled chat is retried after BACKOFF_S before it fails; each attempt is one request.

Run through the runner, live, after `make gcp-cost-check` and `make gcp-usage-check` (from services/semantic-agent):
  GCP_PROJECT=pplk8s-lab-001 DBT_DBNAME=dbt_dev uv run python ../../docs/research/semantic-bet/probes/328_mcp_live.py \
    --agent 354_data_agent.py --arm native-kc [--runs 3] [--requests 100] [--minutes 35] [case id...]
`--legacy <arm>...` (run from the repo root as `python3 -I`): republish each arm's agent with its published context
plus the `legacy` tables, which RULE.md puts in reach of every SQL arm; everything else in the context is kept.
`--copy <arm>...` (the same way): create or update `bet-context` from `pplk8s-semantic`'s published context (our
generated context, PR #310's publish.py) and `bet-governed` from `pplk8s-governed`'s, each with the legacy tables;
and #357's equal-reach arms: `bet-kc-reach` (bet-kc's context on bet-context's tables) and `bet-context-bare`
(bet-context's without its verified queries); the source agents are only read.
Env: GCP_PROJECT (required); the credential as platform/gcp/data-agent/publish.py picks it (on cloud the proxy
injects it).
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import re
import sys
import time
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
# The model a data agent answers with: Google's, chosen by the service (`options.model: MODEL_UNSPECIFIED`), never
# the runner's MODEL_ID; logged as the rows' `model`, so the report never pairs these arms with an OpenRouter one.
# The chat request takes two Gemini switches (v1 discovery, read 2026-11-04): `model` (MODEL_UNSPECIFIED, "either
# preview or non preview model can be used", or LATEST_GA_MODEL, "the most up-to-date non-preview model") and
# `thinkingMode` (THINKING_MODE_UNSPECIFIED, FAST or THINKING). BET_DATA_AGENT_MODEL and BET_DATA_AGENT_THINKING
# set them per pass; a pass with either set logs its own model name, so its runs score as a separate model.
CHAT_MODEL = os.environ.get("BET_DATA_AGENT_MODEL", "MODEL_UNSPECIFIED")
THINKING = os.environ.get("BET_DATA_AGENT_THINKING", "")
if CHAT_MODEL not in ("MODEL_UNSPECIFIED", "LATEST_GA_MODEL") or THINKING not in (
    "",
    "FAST",
    "THINKING",
):
    sys.exit(
        f"354_data_agent: unknown BET_DATA_AGENT_MODEL {CHAT_MODEL!r} or BET_DATA_AGENT_THINKING {THINKING!r}"
    )
MODEL = f"google-data-agent ({CHAT_MODEL}{', ' + THINKING if THINKING else ''})"
# Each data-agent arm's agent, in RULE.md's rung order.
AGENTS = {
    "native-context": "bet-context",
    "native-governed": "bet-governed",
    "native-kc": "bet-kc",
    "native-shaped": "bet-shaped",
    "native-graph": "bet-graph",
    "native-kc-max": "bet-kc-max",  # 360_kc_max.py --publish
    "native-bare": "bet-bare",  # 372_bare_agent.py --publish: the tables only
    # #357's equal-reach arms, published by `--copy`.
    "native-kc-reach": "bet-kc-reach",
    "native-context-bare": "bet-context-bare",
    # bet-context with Python analysis on (owner, 2026-11-07), published by `--copy`.
    "native-context-python": "bet-context-python",
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


# The data agent's answer when the project's daily BigQuery query quota (`QueryUsagePerDay`, platform/gcp/infra/
# bigquery.tf's hard stop, never raised) refused its query: the lab's limit, not the arm's answer (#364, 2026-11-03,
# 129 runs from 22:03Z); matched in every wording the agent used then, and in no logged answer before it.
QUOTA_ANSWER = re.compile(
    r"QueryUsagePer\w*Day|daily[\w' ]{0,30}custom[\w ]{0,30}quota|custom[\w ]{0,30}quota[\w ()`]{0,40}exceeded",
    re.IGNORECASE,
)


def quota_failure(answer: str) -> dict[str, Any] | None:
    """A turn answered with the daily query quota's refusal, as the runner's `daily_quota` failure: no later chat can
    query until the quota's day resets, so it ends the pass and the run is asked again on a later one."""
    if not QUOTA_ANSWER.search(answer):
        return None
    message = f"BigQuery QueryUsagePerDay: {answer[:300]}"
    return {"kind": "daily_quota", "message": message, "retry_after_s": None}


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
    calls += [
        {"tool": "python_analysis", "args": {"code": code}}
        for code in summary.get("python_code") or []
    ]
    return {
        "question": question,
        "calls": calls,
        "answer": "\n".join(summary["final_response"]).strip(),
        "thought": "\n".join(t for t in summary["texts"] if t.startswith("THOUGHT")),
        "model_calls": 1,
    }


# A result's head in the log, as the local setups keep their tool results (bet_eval.RESULT_HEAD).
RESULT_HEAD = 400


def trace_of(stream: Any) -> dict[str, Any]:
    """What a turn's stream holds besides its answer (#440): each result's head, the BigQuery job
    ids and the follow-up questions the agent offered; logged beside the answer, never scored."""
    results, jobs, followups = [], [], []
    for message in stream if isinstance(stream, list) else [stream]:
        system = message.get("systemMessage") if isinstance(message, dict) else None
        if not isinstance(system, dict):
            continue
        data = system.get("data") or {}
        if "result" in data:
            rows = (data["result"] or {}).get("data")
            results.append(json.dumps(rows, default=str)[:RESULT_HEAD])
        if job := (data.get("bigQueryJob") or {}).get("jobId"):
            jobs.append(job)
        text = system.get("text") or {}
        if text.get("textType") == "FOLLOWUP_QUESTIONS":
            followups += list(text.get("parts") or [])
    return {
        k: v
        for k, v in (("results", results), ("jobs", jobs), ("followups", followups))
        if v
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
            turn = {
                **turn_of(question, shaped.summarise(stream)),
                **trace_of(stream),
                "model_calls": attempts,
            }
            if failed := quota_failure(turn["answer"]):
                turns.append({**turn, "failure": failed})
                break
            turns.append(turn)
        return turns

    async def ask(questions: Sequence[str]) -> list[dict[str, Any]]:
        import anyio  # the runner's venv has it; --legacy runs on the system Python

        return await anyio.to_thread.run_sync(conversation, questions)

    return ask


# The status a chat that failed on the network (no HTTP answer) is given: an `error` failure.
NETWORK = 599
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
    if CHAT_MODEL != "MODEL_UNSPECIFIED":
        body["model"] = CHAT_MODEL
    if THINKING:
        body["thinkingMode"] = THINKING
    started = time.monotonic()
    try:
        status, payload = send(
            "POST",
            f"https://geminidataanalytics.{shaped.LOCATION}.rep.googleapis.com/v1/{parent}:chat",
            body,
        )
    except (OSError, http.client.HTTPException) as error:
        # A dropped stream (measured 2026-11-03T20:25Z: `ConnectionResetError` mid-chunk ended a pass): a failed
        # chat the runner asks again on a later pass, never the end of the pass.
        status, payload = NETWORK, {"error": f"{type(error).__name__}: {error}"}
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
# #357's arms, each derived from bet agents' published contexts (read, never written), so it differs from its
# source arm in one thing only: `bet-kc-reach` is bet-kc's context (its one-line instruction, no authored context)
# on bet-context's tables (the legacy ones included); `bet-context-bare` is bet-context's without its verified
# queries (its glossary terms and system instruction kept).
DERIVED = {
    "native-kc-reach": ("bet-kc", "bet-context"),
    "native-context-bare": ("bet-context",),
    "native-context-python": ("bet-context",),
}


def published_tables(agent: dict[str, Any]) -> list[str]:
    """The `dataset.table` names an agent's published context references."""
    context = (agent.get("dataAnalyticsAgent") or {}).get("publishedContext") or {}
    refs = ((context.get("datasourceReferences") or {}).get("bq") or {}).get(
        "tableReferences"
    ) or []
    return [f"{r['datasetId']}.{r['tableId']}" for r in refs]


def derived_context(arm: str, published: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """A #357 arm's context from its sources' published contexts (by agent id)."""
    if arm == "native-context-bare":
        context = json.loads(json.dumps(published["bet-context"]))
        context.pop("exampleQueries", None)
        return context
    if arm == "native-context-python":
        # bet-context's context with one change: the agent may run Python on its query results.
        context = json.loads(json.dumps(published["bet-context"]))
        options = context.setdefault("options", {})
        options.setdefault("analysis", {})["python"] = {"enabled": True}
        return context
    if arm == "native-kc-reach":
        context = json.loads(json.dumps(published["bet-kc"]))
        context["datasourceReferences"] = json.loads(
            json.dumps(published["bet-context"]["datasourceReferences"])
        )
        return context
    raise SystemExit(f"354_data_agent: no derived context for {arm}")


def copy_agent(arm: str) -> int:
    """Publish the arm's bet agent: from its source agent's published context plus the legacy tables, or (#357's
    arms) from the bet agents it is derived from."""
    if arm not in SOURCES and arm not in DERIVED:
        sys.exit(
            f"354_data_agent: --copy takes {sorted([*SOURCES, *DERIVED])}, not {arm}"
        )
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    shaped = _shaped()
    publish = shaped.load_publish()
    send = publish.http_transport(publish.access_token(dict(os.environ)), project)
    base = f"{publish.endpoint(shaped.LOCATION)}/v1/projects/{project}/locations/{shaped.LOCATION}/dataAgents"
    sources = DERIVED.get(arm) or (SOURCES[arm],)
    published = {}
    for source in sources:
        reader = publish.Publisher(send, project, shaped.LOCATION, source)
        current = reader.call("GET", f"{base}/{source}")
        published[source] = (current.get("dataAnalyticsAgent") or {}).get(
            "publishedContext"
        ) or {}
        if not published[source]:
            print(f"354_data_agent: {source} has no published context")
            return 2
    if arm in DERIVED:
        context = derived_context(arm, published)
        what = f"derived from {' and '.join(sources)} (#357)"
    else:
        context = with_legacy(published[sources[0]], project)
        what = f"{sources[0]}'s published context plus the legacy tables"
    agent = publish.desired(
        context,
        None,
        display_name=f"bet {arm}",
        description=f"The semantic bet's {arm} arm: {what}.",
    )
    publisher = publish.Publisher(send, project, shaped.LOCATION, AGENTS[arm])
    try:
        writes = publisher.publish(agent)
    except publish.PublishError as error:
        print(f"354_data_agent: {AGENTS[arm]} publish refused: {error}")
        return 2
    again = publisher.call("GET", f"{base}/{AGENTS[arm]}")
    kept = (again.get("dataAnalyticsAgent") or {}).get("publishedContext") or {}
    print(
        f"354_data_agent: {AGENTS[arm]} {what}: writes {writes}; "
        f"published tables {published_tables(again)}; "
        f"verified queries {len(kept.get('exampleQueries') or [])}, "
        f"glossary terms {len(kept.get('glossaryTerms') or [])}, "
        f"system instruction {len(kept.get('systemInstruction') or '')} characters"
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
    # --copy <arm>...: publish bet-context / bet-governed from the main track's agents, or #357's arms.
    actions = {"--legacy": give_legacy, "--copy": copy_agent}
    if sys.argv[1:2] not in ([a] for a in actions) or not sys.argv[2:]:
        sys.exit("usage: 354_data_agent.py --legacy|--copy <arm>...")
    action = actions[sys.argv[1]]
    raise SystemExit(max(action(arm) for arm in sys.argv[2:]))
