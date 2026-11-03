"""Claude as a model backend (#361) with no network: a local stand-in answers Anthropic's
`/v1/messages`. The key comes only from BET_ANTHROPIC_API_KEY and the base URL only from the
module, Fable is refused, a missing key skips the pass, every call is priced from its usage, and a
pass stops before its dollar budget would be crossed."""

import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from google.adk.agents import LlmAgent

from semantic_agent import agent as semantic
from semantic_agent import bet_eval, model, spend, tools
from semantic_agent.model import MissingKey, build_model, classify, failure_of
from semantic_agent.spend import BudgetSpent, Meter, Usage, priced
from tests.conftest import final_text, run_turn
from tests.test_bet_eval import BET, EXPECTED, Answers

# A stand-in value only: never a real key, and never ANTHROPIC_API_KEY.
TEST_KEY = "test-bet-key-not-real"


class RecordingEnviron(dict):
    """os.environ that remembers every name read."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read: set[str] = set()

    def get(self, key, default=None):
        self.read.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.read.add(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        self.read.add(key)
        return super().__contains__(key)


@pytest.fixture
def anthropic(monkeypatch, tmp_path):
    """A local stand-in for api.anthropic.com: every request is kept and answered with a text
    message carrying `served["usage"]`; the meter logs to a temporary file."""
    served = {
        "requests": [],
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 50,
        },
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            served["requests"].append(
                {"path": self.path, "key": self.headers.get("x-api-key"), "body": body}
            )
            out = json.dumps(
                {
                    "id": f"msg_{len(served['requests'])}",
                    "type": "message",
                    "role": "assistant",
                    "model": body["model"],
                    "content": [{"type": "text", "text": "Revenue was 868.65 EUR."}],
                    "stop_reason": "end_turn",
                    "usage": served["usage"],
                }
            ).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(model, "ANTHROPIC_API_BASE", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("BET_ANTHROPIC_API_KEY", TEST_KEY)
    # The session's own Claude Code base URL must never be used: point it at a closed port.
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("MODEL_RETRIES", "0")
    monkeypatch.setattr(spend, "METER", Meter(log=tmp_path / "calls.jsonl"))
    yield served
    server.shutdown()


def claude_agent(model_id: str = "claude-haiku-5-5") -> LlmAgent:
    return LlmAgent(
        name="claude_test",
        model=build_model("anthropic", model_id),
        instruction="Answer the question.",
        on_model_error_callback=model.answer_model_failure,
    )


def test_the_key_and_base_url_are_passed_explicitly_with_prompt_caching(monkeypatch):
    monkeypatch.setenv("BET_ANTHROPIC_API_KEY", TEST_KEY)
    llm = build_model("anthropic", "claude-sonnet-5-5")
    args = llm._additional_args
    assert llm.model == "anthropic/claude-sonnet-5-5"
    assert args["api_key"] == TEST_KEY
    assert args["api_base"] == "https://api.anthropic.com"
    assert args["cache_control_injection_points"] == [
        {"location": "message", "role": "system"},
        {"location": "message", "index": -1},
    ]
    assert TEST_KEY not in repr(llm)


def test_a_call_reaches_the_base_url_with_the_bet_key_and_never_reads_anthropic_api_key(
    anthropic, monkeypatch
):
    environ = RecordingEnviron(os.environ)
    monkeypatch.setattr(os, "environ", environ)
    events = run_turn(claude_agent(), "Revenue on 2 October 2026?")

    assert final_text(events) == "Revenue was 868.65 EUR."
    (request,) = anthropic["requests"]
    assert request["path"] == "/v1/messages"
    assert request["key"] == TEST_KEY
    assert request["body"]["model"] == "claude-haiku-5-5"
    # The stable prefix is marked for caching: the system instruction (tools render before it).
    assert request["body"]["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "ANTHROPIC_API_KEY" not in environ.read
    assert "ANTHROPIC_AUTH_TOKEN" not in environ.read


def test_every_call_is_priced_from_its_usage_and_logged(anthropic):
    run_turn(claude_agent(), "Revenue on 2 October 2026?")

    ((name, usage),) = spend.METER.calls
    assert name == "claude-haiku-5-5"
    assert (usage.input, usage.output, usage.cache_read, usage.cache_write) == (10, 5, 100, 50)
    assert usage.dollars == pytest.approx((10 * 0.10 + 5 * 0.50 + 100 * 0.01 + 50 * 0.125) / 1e6)
    (row,) = spend.read_jsonl(spend.METER.log)
    assert row["model"] == "claude-haiku-5-5" and row["cache_write"] == 50
    assert TEST_KEY not in spend.METER.log.read_text()


@pytest.mark.parametrize("model_id", ["claude-fable-5-1", "claude-fable-5"])
def test_fable_is_refused(monkeypatch, model_id):
    monkeypatch.setenv("BET_ANTHROPIC_API_KEY", TEST_KEY)
    with pytest.raises(ValueError, match="Fable"):
        build_model("anthropic", model_id)


def test_only_the_three_priced_models_are_allowed(monkeypatch):
    monkeypatch.setenv("BET_ANTHROPIC_API_KEY", TEST_KEY)
    with pytest.raises(ValueError, match="must be one of"):
        build_model("anthropic", "claude-opus-5")
    assert set(spend.PRICES) == {"claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"}


def test_a_missing_key_skips_the_claude_pass_with_that_reason(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("BET_ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingKey, match="BET_ANTHROPIC_API_KEY is unset"):
        build_model("anthropic", "claude-haiku-5-5")

    monkeypatch.setenv("MODEL_BACKEND", "anthropic")
    monkeypatch.setenv("MODEL_ID", "claude-haiku-5-5")
    log = tmp_path / "probe.jsonl"
    assert asyncio.run(bet_eval.main(["--log", str(log), "revenue_one_day"])) == 3
    assert "skipped: BET_ANTHROPIC_API_KEY is unset" in capsys.readouterr().out
    assert not log.exists()


@pytest.mark.parametrize(
    ("model_id", "usage", "dollars"),
    [
        # Haiku 5.5: $0.10 in, $0.125 cache write, $0.01 cache read, $0.50 out.
        ("claude-haiku-5-5", Usage(50_000, 50_000, 0, 0), 0.03),
        ("claude-haiku-5-5", Usage(0, 0, 40_000, 40_000), 0.0054),
        # A prompt over 100,000 tokens: Haiku's long-context prices on the whole call.
        (
            "claude-haiku-5-5",
            Usage(60_000, 1_000, 50_000, 0),
            (60e3 * 0.5 + 1e3 * 2.5 + 50e3 * 0.05) / 1e6,
        ),
        # Sonnet 5.5: $2, $2.50, $0.10, $10.
        (
            "claude-sonnet-5-5",
            Usage(12_000, 2_000, 30_000, 4_000),
            (24e3 + 20e3 + 3e3 + 10e3) / 1e6,
        ),
        # Opus 5.5: $4, $5, $0.20, $20.
        ("claude-opus-5-5", Usage(12_000, 2_000, 30_000, 4_000), (48e3 + 40e3 + 6e3 + 20e3) / 1e6),
    ],
)
def test_pricing_from_a_stub_usage(model_id, usage, dollars):
    assert priced(model_id, usage).dollars == pytest.approx(dollars)


def test_a_call_the_budget_cannot_cover_is_never_sent(anthropic):
    # Each call costs 50,000 uncached input tokens on Sonnet: $0.10.
    anthropic["usage"] = {"input_tokens": 50_000, "output_tokens": 0}
    spend.METER.start("test", budget=0.15, log=spend.METER.log)
    agent = claude_agent("claude-sonnet-5-5")

    first = run_turn(agent, "Revenue on 2 October 2026?")
    second = run_turn(agent, "Revenue on 3 October 2026?")

    assert final_text(first) == "Revenue was 868.65 EUR."
    assert len(anthropic["requests"]) == 1
    assert failure_of(second).kind == "budget"
    assert "dollar budget is spent" in final_text(second)
    assert spend.METER.spent == pytest.approx(0.10)
    assert spend.METER.stopped


def test_a_budget_stop_and_a_billing_refusal_end_the_run():
    assert classify(BudgetSpent("spent")).ends_run
    billing = classify(RuntimeError("Your credit balance is too low to access the Anthropic API"))
    assert billing.kind == "billing" and billing.ends_run
    assert (
        "[redacted]" in classify(RuntimeError("bad key " + "sk-" + "ant-api03-abc_DEF-123")).message
    )


class Metered(Answers):
    """The scripted answers, each call checked against and counted by the meter like Claude's."""

    async def generate_content_async(self, llm_request, stream=False):
        spend.METER.check("claude-haiku-5-5")
        async for response in super().generate_content_async(llm_request, stream):
            spend.METER.record("claude-haiku-5-5", Usage(input=50_000, output=70_000, calls=1))
            yield response


def test_the_runner_stops_the_pass_before_the_next_case_would_cross_its_budget(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(tools, "run", lambda query, catalog: {"rows": [{"revenue_eur": 868.65}]})
    monkeypatch.setattr(spend, "METER", Meter(log=tmp_path / "calls.jsonl"))
    # Every case-run costs $0.04 (one call, 50k in and 70k out): two fit in $0.10, a third not.
    spend.METER.start("test", budget=0.10, log=spend.METER.log)
    llm = Metered()
    llm.asked = []
    agents = {"custom-metricflow": semantic.build_agent(llm)}
    log = tmp_path / "probe.jsonl"

    why = asyncio.run(bet_eval.run_bet(BET, EXPECTED, agents, {}, "claude-haiku-5-5", 3, log))

    entries = bet_eval.read_log(log)
    assert why == "budget"
    assert len(entries) == 2
    assert all(e["usage"]["dollars"] == pytest.approx(0.04) for e in entries)
    assert spend.METER.spent <= 0.10
    # A pass's anomaly checks: none fired within the budget.
    assert spend.anomalies(spend.METER, 0.10, spend.METER.spent, {}) == []


def test_the_anomaly_checks_fire_on_each_owner_condition():
    meter = Meter(log=None)
    meter.start("p", budget=0.01, log=None)
    meter.record("claude-opus-5-5", Usage(input=10_000, output=1_000, calls=1))
    meter.failure("claude-opus-5-5", classify(RuntimeError("Your credit balance is too low")))
    found = spend.anomalies(meter, 0.01, 81.0, {"claude-opus-5-5": 2_000})
    assert any(f.startswith("over budget") for f in found)
    assert any("over 3 x the probe's per-case median" in f for f in found)
    assert any(f.startswith("billing error") for f in found)
    assert any("past $80.00" in f for f in found)


def test_a_pass_appends_its_row_to_the_ledger(tmp_path):
    meter = Meter(log=tmp_path / "calls.jsonl")
    meter.start("probe haiku", budget=1.0, log=meter.log)
    meter.record("claude-haiku-5-5", Usage(input=12_000, output=2_000, calls=1))
    ledger = tmp_path / "spend.md"
    ledger.write_text("| header |\n")

    found = spend.finish_pass(
        meter, ledger, meter.log, tmp_path / "probe.jsonl", note="stopped: done"
    )

    row = ledger.read_text().splitlines()[-1]
    assert found == []
    assert "probe haiku (stopped: done)" in row and "$0.0022" in row and "| none |" in row
