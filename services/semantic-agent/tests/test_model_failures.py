"""A spent quota, per minute or per day, ends the turn with an answer that says so, and the eval
waits out a per-minute limit once and stops sending at a per-day one (semantic/PLAN.md SL-5)."""

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import litellm
import pytest
from google.genai import errors

from semantic_agent import agent as semantic
from semantic_agent import evaluation, tools
from semantic_agent.evaluation import ANSWER_CORRECT, METRIC_CHOICE, eval_cases
from semantic_agent.model import build_model, classify, failure_of
from sql_baseline import agent as baseline
from tests.conftest import ScriptedLlm, final_text, run_turn
from tests.test_evaluation import EXPECTED, QUESTIONS, AnswersByQuestion


def openrouter_429(limit: str, reset_s: float) -> dict:
    """OpenRouter's body for a spent free-tier limit (`free-models-per-min` or `-per-day`)."""
    reset_ms = str(int((time.time() + reset_s) * 1000))
    return {
        "error": {
            "message": f"Rate limit exceeded: {limit}. ",
            "code": 429,
            "metadata": {
                "headers": {
                    "X-RateLimit-Limit": "50",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": reset_ms,
                },
                "provider_name": None,
            },
        }
    }


@pytest.fixture
def openrouter(monkeypatch):
    """A local stand-in for OpenRouter that answers every request with `served["body"]` and 429."""
    served = {"body": {}, "requests": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length", 0)))
            served["requests"] += 1
            body = json.dumps(served["body"]).encode()
            self.send_response(429)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("OPENROUTER_API_BASE", f"http://127.0.0.1:{server.server_port}/api/v1")
    monkeypatch.setenv("MODEL_RETRIES", "1")
    yield served
    server.shutdown()


@pytest.mark.parametrize("build", [semantic.build_agent, baseline.build_agent])
@pytest.mark.parametrize(
    ("limit", "reset_s", "kind", "says"),
    [
        ("free-models-per-day", 6 * 3600, "daily_quota", "daily request quota is spent"),
        ("free-models-per-min", 40, "rate_limit", "ask again in"),
    ],
)
def test_a_spent_quota_ends_the_turn_with_an_answer(openrouter, build, limit, reset_s, kind, says):
    """Through the real LiteLLM client: no exception out of the runner, no wait for the reset."""
    openrouter["body"] = openrouter_429(limit, reset_s)
    started = time.monotonic()
    events = run_turn(build(build_model("openrouter", "some/model:free")), "Revenue yesterday?")
    assert time.monotonic() - started < 30
    assert openrouter["requests"] == 2  # the first call and MODEL_RETRIES=1
    assert says in final_text(events)
    failure = failure_of(events)
    assert failure.kind == kind
    assert 0 < failure.retry_after_s <= reset_s


@pytest.mark.parametrize(
    ("quota_id", "kind"),
    [
        ("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "daily_quota"),
        ("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "rate_limit"),
    ],
)
def test_gemini_quota_errors_are_read_too(quota_id, kind):
    error = errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "You exceeded your current quota.",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [{"quotaId": quota_id}],
                    },
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "40s"},
                ],
            }
        },
    )
    failure = classify(error)
    assert (failure.kind, failure.retry_after_s) == (kind, 40.0)


def test_any_other_model_error_is_answered_too():
    failure = classify(TimeoutError("read timed out"))
    assert failure.kind == "error"
    assert "read timed out" in failure.answer()


def rate_limit_error(limit: str, reset_s: float) -> litellm.RateLimitError:
    body = json.dumps(openrouter_429(limit, reset_s))
    return litellm.RateLimitError(body, llm_provider="openrouter", model="some/model:free")


class FailsFirst(AnswersByQuestion):
    """Raises the given errors on its first model calls, then answers as AnswersByQuestion."""

    errors: list = []
    calls: int = 0

    async def generate_content_async(self, llm_request, stream=False):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        async for response in super().generate_content_async(llm_request, stream):
            yield response


@pytest.fixture
def waits(monkeypatch):
    monkeypatch.setattr(tools, "run", lambda query, catalog: {"rows": [{"revenue_eur": 868.65}]})
    waited = []

    async def wait(seconds):
        waited.append(seconds)

    monkeypatch.setattr(evaluation, "_wait", wait)
    return waited


def run_eval(model):
    cases = eval_cases(QUESTIONS, EXPECTED, "semantic_agent", semantic=True)
    agent = semantic.build_agent(model)
    return asyncio.run(evaluation.evaluate(agent, cases, [ANSWER_CORRECT, METRIC_CHOICE]))


def test_the_eval_waits_out_a_per_minute_limit_once_and_scores_the_rerun(waits):
    outcomes = run_eval(FailsFirst(errors=[rate_limit_error("free-models-per-min", 30)]))
    assert len(waits) == 1 and 30 <= waits[0] <= 32
    assert outcomes["revenue_one_day"].scores == {"answer_correct": 1.0, "metric_choice": 1.0}
    assert outcomes["amsterdam_temperature"].scores["answer_correct"] == 1.0


def test_the_eval_bounds_its_wait_and_reports_a_limit_that_holds(waits):
    limit = rate_limit_error("free-models-per-min", 3600)
    outcomes = run_eval(FailsFirst(errors=[limit, limit]))
    assert waits == [evaluation.MAX_WAIT_S + 1]
    assert "rate-limited" in outcomes["revenue_one_day"].error
    assert not outcomes["revenue_one_day"].skipped
    assert outcomes["amsterdam_temperature"].scores["answer_correct"] == 1.0


def test_the_eval_stops_sending_once_the_daily_quota_is_spent(waits):
    model = FailsFirst(errors=[rate_limit_error("free-models-per-day", 6 * 3600)])
    outcomes = run_eval(model)
    assert model.calls == 1  # the second question was never sent
    assert waits == []
    first, second = outcomes["revenue_one_day"], outcomes["amsterdam_temperature"]
    assert "daily request quota is spent" in first.error and not first.skipped
    assert second.skipped and "daily request quota is spent" in second.error
    text = evaluation.report(QUESTIONS, EXPECTED, outcomes, {}, "scripted")
    assert "| skipped |" in text


def test_a_scripted_model_never_carries_a_failure():
    events = run_turn(semantic.build_agent(ScriptedLlm(steps=["fine"])), "q")
    assert failure_of(events) is None
