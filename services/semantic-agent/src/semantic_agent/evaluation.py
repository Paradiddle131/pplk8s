"""The scored eval (semantic/PLAN.md SL-5): the semantic agent and the text-to-SQL baseline on the
same questions and the same model, through ADK's own eval engine (`LocalEvalService`).

`evals/questions.yaml` holds the questions; each one's expected numbers come from the warehouse
when the run starts. Three custom ADK metrics score a run:
- `answer_correct`: the final answer carries an expected number; for the semantic agent on a
  question no metric covers, it says the semantic layer has no such metric instead. Numbers inside
  a quoted freshness statement do not count.
- `metric_choice` (semantic agent only): its `query_metrics` calls named the expected metrics.
- `freshness_quoted` (semantic agent only, SL-4): the answer quotes every freshness statement its
  `query_metrics` calls returned.

Usage (`make agent-eval` sets the env): python -m semantic_agent.evaluation [question ids]
Writes the scores side by side to stdout and to `docs/research/semantic-agent-eval.md`; a run the
model's daily quota cut short prints what it got, leaves the report as it was and exits 3.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import yaml
from google.adk.agents import LlmAgent
from google.adk.evaluation.base_eval_service import (
    EvaluateConfig,
    EvaluateRequest,
    InferenceConfig,
    InferenceRequest,
    InferenceResult,
    InferenceStatus,
)
from google.adk.evaluation.eval_case import (
    EvalCase,
    IntermediateData,
    Invocation,
    SessionInput,
    get_all_tool_calls,
    get_all_tool_responses,
)
from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_metrics import EvalMetric
from google.adk.evaluation.evaluator import EvalStatus, EvaluationResult, PerInvocationResult
from google.adk.evaluation.in_memory_eval_sets_manager import InMemoryEvalSetsManager
from google.adk.evaluation.local_eval_service import LocalEvalService
from google.adk.evaluation.metric_evaluator_registry import (
    MetricEvaluatorRegistry,
    register_custom_metrics_from_config,
)
from google.adk.sessions import InMemorySessionService
from google.genai import types

from semantic_agent.model import ModelFailure, failure_of

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "evals" / "questions.yaml"
# The metrics and their code: also what `adk eval ... --config_file_path` takes.
EVAL_CONFIG = EvalConfig.model_validate_json((ROOT / "evals" / "eval_config.json").read_text())
REPORT = ROOT.parents[1] / "docs" / "research" / "semantic-agent-eval.md"

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATES = re.compile(
    rf"\d{{4}}-\d{{2}}-\d{{2}}|\b\d{{1,2}}(?:st|nd|rd|th)?(?:\s+(?:and|to|-|–)\s+\d{{1,2}}(?:st|nd|rd|th)?)?"
    rf"\s+(?:of\s+)?(?:{MONTHS})(?:,?\s+\d{{4}})?|\b(?:{MONTHS})\s+\d{{1,2}}(?!\d)(?:st|nd|rd|th)?"
    rf"(?:\s*(?:and|to|-|–)\s*\d{{1,2}})?(?:,?\s+\d{{4}})?|\b(?:{MONTHS})\s+\d{{4}}",
    re.IGNORECASE,
)
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
DECLINE = re.compile(
    r"no (?:such |\w+ )?metric|not (?:available|defined|covered|in the semantic layer)|"
    r"(?:does not|doesn't|do not|don't) (?:have|define|include|cover|contain)|"
    r"(?:cannot|can't|unable to) (?:answer|be answered|give|report)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    expected_sql: str
    metrics: list[str]


def load_questions(ids: list[str] | None = None) -> list[Question]:
    questions = [Question(**q) for q in yaml.safe_load(QUESTIONS.read_text())["questions"]]
    return [q for q in questions if not ids or q.id in ids]


def expected_numbers(questions: list[Question], url: str) -> dict[str, list[float]]:
    """Each question's expected number from the warehouse, a rate also as a percentage."""
    found = {}
    with psycopg.connect(url) as conn:
        for q in questions:
            (value,) = conn.execute(q.expected_sql).fetchone()  # type: ignore[arg-type, misc]
            value = float(value)
            found[q.id] = [value, round(value * 100, 2)] if 0 < value < 1 else [value]
    return found


def _stated(text: str) -> list[tuple[float, int]]:
    """The numbers an answer states with their decimals, dates left out."""
    found = []
    for raw in NUMBER.findall(DATES.sub(" ", text)):
        raw = raw.replace(",", "")
        found.append((float(raw), len(raw.partition(".")[2])))
    return found


def numbers_in(text: str) -> list[float]:
    return [n for n, _ in _stated(text)]


def carries(text: str, expected: list[float]) -> bool:
    """An expected number within half a cent, or rounded to the decimals the answer states."""
    return any(
        abs(n - e) <= 0.006 or (decimals >= 1 and round(e, decimals) == n)
        for n, decimals in _stated(text)
        for e in expected
    )


def _text(content: types.Content | None) -> str:
    """The answer's text, without the model's reasoning (thought parts)."""
    return "".join(p.text or "" for p in (content.parts or []) if not p.thought) if content else ""


def _spec(expected: Invocation) -> dict[str, Any]:
    return json.loads(_text(expected.final_response))


def _result(scores: list[float], actual: list[Invocation], expected: list[Invocation]):
    status = EvalStatus.PASSED if all(s == 1.0 for s in scores) else EvalStatus.FAILED
    per = [
        PerInvocationResult(
            actual_invocation=a,
            expected_invocation=e,
            score=s,
            eval_status=EvalStatus.PASSED if s == 1.0 else EvalStatus.FAILED,
        )
        for a, e, s in zip(actual, expected, scores, strict=True)
    ]
    overall = sum(scores) / len(scores) if scores else None
    return EvaluationResult(
        overall_score=overall, overall_eval_status=status, per_invocation_results=per
    )


def freshness_statements(invocation: Invocation) -> list[str]:
    """The freshness statements the invocation's query_metrics calls returned, in order."""
    found = []
    for response in get_all_tool_responses(invocation.intermediate_data):
        statement = ((response.response or {}).get("freshness") or {}).get("statement")
        if response.name == "query_metrics" and statement and statement not in found:
            found.append(statement)
    return found


def _squash(text: str) -> str:
    return " ".join(text.split())


def answer_correct(eval_metric, actual_invocations, expected_invocations, conversation_scenario):
    """1 when the answer carries an expected number, or declines where it should."""
    scores = []
    for actual, expected in zip(actual_invocations, expected_invocations or [], strict=True):
        spec, text = _spec(expected), _squash(_text(actual.final_response))
        for statement in freshness_statements(actual):
            text = text.replace(_squash(statement), " ")
        if spec["decline"]:
            right = bool(DECLINE.search(text)) and not carries(text, spec["expected"])
        else:
            right = carries(text, spec["expected"])
        scores.append(1.0 if right else 0.0)
    return _result(scores, actual_invocations, expected_invocations or [])


def queried_metrics(invocation: Invocation) -> set[str]:
    return {
        name
        for use in get_all_tool_calls(invocation.intermediate_data)
        if use.name == "query_metrics"
        for name in (use.args or {}).get("metrics", [])
    }


def metric_choice(eval_metric, actual_invocations, expected_invocations, conversation_scenario):
    """1 when the semantic agent's queries named every expected metric."""
    scores = [
        1.0 if set(_spec(expected)["metrics"]) <= queried_metrics(actual) else 0.0
        for actual, expected in zip(actual_invocations, expected_invocations or [], strict=True)
    ]
    return _result(scores, actual_invocations, expected_invocations or [])


def freshness_quoted(eval_metric, actual_invocations, expected_invocations, conversation_scenario):
    """1 when the answer quotes each freshness statement its queries returned; a question a metric
    covers needs at least one."""
    scores = []
    for actual, expected in zip(actual_invocations, expected_invocations or [], strict=True):
        statements = freshness_statements(actual)
        text = _squash(_text(actual.final_response))
        quoted = all(_squash(s) in text for s in statements)
        needed = bool(_spec(expected)["metrics"])
        scores.append(1.0 if quoted and (statements or not needed) else 0.0)
    return _result(scores, actual_invocations, expected_invocations or [])


ANSWER_CORRECT = EvalMetric(metric_name="answer_correct", threshold=1.0)
METRIC_CHOICE = EvalMetric(metric_name="metric_choice", threshold=1.0)
FRESHNESS_QUOTED = EvalMetric(metric_name="freshness_quoted", threshold=1.0)


def eval_cases(
    questions: list[Question], expected: dict[str, list[float]], app_name: str, semantic: bool
) -> list[EvalCase]:
    cases = []
    for q in questions:
        spec = {
            "expected": expected[q.id],
            "metrics": q.metrics,
            "decline": semantic and not q.metrics,
        }
        uses = [types.FunctionCall(name="query_metrics", args={"metrics": q.metrics})]
        invocation = Invocation(
            user_content=types.Content(role="user", parts=[types.Part(text=q.question)]),
            final_response=types.Content(role="model", parts=[types.Part(text=json.dumps(spec))]),
            intermediate_data=IntermediateData(tool_uses=uses if semantic and q.metrics else []),
        )
        cases.append(
            EvalCase(
                eval_id=q.id,
                conversation=[invocation],
                session_input=SessionInput(app_name=app_name, user_id="eval"),
            )
        )
    return cases


@dataclass
class CaseOutcome:
    answer: str
    scores: dict[str, float | None]
    error: str | None = None
    skipped: bool = False  # never sent: the model's daily quota was spent before it


# A rate-limited question waits out the limit once, at most this long, then runs again.
MAX_WAIT_S = 90.0


async def _wait(seconds: float) -> None:
    await asyncio.sleep(seconds)


async def evaluate(agent: LlmAgent, cases: list[EvalCase], metrics: list[EvalMetric]):
    """Runs the cases through ADK's LocalEvalService, one at a time (the free tier's rate limit).

    A case the model rate-limits waits out the limit (at most MAX_WAIT_S) and runs once more; once
    the daily quota is spent, the cases left are skipped with that reason, never sent.
    """
    app_name = agent.name
    manager = InMemoryEvalSetsManager()
    manager.create_eval_set(app_name, "questions")
    for case in cases:
        manager.add_eval_case(app_name, "questions", case)
    registry = register_custom_metrics_from_config(EVAL_CONFIG, MetricEvaluatorRegistry())
    sessions = InMemorySessionService()
    service = LocalEvalService(
        root_agent=agent,
        eval_sets_manager=manager,
        metric_evaluator_registry=registry,
        session_service=sessions,
    )

    async def infer(case: EvalCase) -> tuple[InferenceResult, ModelFailure | None]:
        request = InferenceRequest(
            app_name=app_name,
            eval_set_id="questions",
            eval_case_ids=[case.eval_id],
            inference_config=InferenceConfig(parallelism=1),
        )
        (result,) = [r async for r in service.perform_inference(inference_request=request)]
        session = None
        if result.session_id:
            session = await sessions.get_session(
                app_name=app_name, user_id="eval", session_id=result.session_id
            )
        return result, failure_of(session.events) if session else None

    outcomes: dict[str, CaseOutcome] = {}
    succeeded: list[InferenceResult] = []
    spent: ModelFailure | None = None
    for case in cases:
        if spent:
            outcomes[case.eval_id] = CaseOutcome("", {}, error=spent.answer(), skipped=True)
            continue
        result, failure = await infer(case)
        if failure and failure.kind == "rate_limit":
            await _wait(min(failure.retry_after_s or 60.0, MAX_WAIT_S) + 1)
            result, failure = await infer(case)
        if result.status != InferenceStatus.SUCCESS:
            outcomes[case.eval_id] = CaseOutcome("", {}, error=result.error_message or "failed")
        elif failure:
            outcomes[case.eval_id] = CaseOutcome("", {}, error=failure.answer())
            spent = failure if failure.kind == "daily_quota" else None
        else:
            succeeded.append(result)
    answers = {r.eval_case_id: _text(r.inferences[-1].final_response) for r in succeeded}
    evaluate_request = EvaluateRequest(
        inference_results=succeeded,
        evaluate_config=EvaluateConfig(eval_metrics=metrics, parallelism=1),
    )
    if succeeded:
        async for result in service.evaluate(evaluate_request=evaluate_request):
            scores = {m.metric_name: m.score for m in result.overall_eval_metric_results}
            outcomes[result.eval_id] = CaseOutcome(answers.get(result.eval_id, ""), scores)
    return outcomes


def report(questions, expected, semantic, baseline, model_id: str) -> str:
    def mark(outcome: CaseOutcome | None, metric: str) -> str:
        if outcome is None:
            return "not run"
        if outcome.skipped:
            return "skipped"
        if outcome.error:
            return "error"
        return "✓" if outcome.scores.get(metric) == 1.0 else "✗"

    with_metric = [q for q in questions if q.metrics]
    without = [q for q in questions if not q.metrics]

    def count(outcomes, subset, metric="answer_correct"):
        return sum(1 for q in subset if mark(outcomes.get(q.id), metric) == "✓")

    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")
    lines = [
        "# Semantic agent eval",
        "",
        f"Run {stamp} by `make agent-eval` (`services/semantic-agent`, semantic/PLAN.md SL-5), "
        f"model `{model_id}`, on `dbt/dev/fixture.sql`.",
        "Each agent answers each question once through ADK's `LocalEvalService`; "
        "an answer is right when it carries the number the warehouse gives "
        "(`evals/questions.yaml`).",
        "",
        "| | Semantic agent | Text-to-SQL baseline |",
        "|---|---|---|",
        f"| Questions a metric covers ({len(with_metric)}) | {count(semantic, with_metric)} right, "
        f"{count(semantic, with_metric, 'metric_choice')} with the expected metric, "
        f"{count(semantic, with_metric, 'freshness_quoted')} quoting their freshness | "
        f"{count(baseline, with_metric)} right |",
        f"| Questions no metric covers ({len(without)}) | {count(semantic, without)} said so | "
        f"{count(baseline, without)} right |",
        f"| All ({len(questions)}) | {count(semantic, questions)} | {count(baseline, questions)} |",
        "",
        "| Question | Expected | Semantic | Metric | Freshness | Baseline |",
        "|---|---|---|---|---|---|",
    ]
    for q in questions:
        number = expected[q.id][0]
        chose = mark(semantic.get(q.id), "metric_choice") if q.metrics else "none"
        quoted = mark(semantic.get(q.id), "freshness_quoted") if q.metrics else "none"
        lines.append(
            f"| `{q.id}` {q.question} | {number:g} | "
            f"{mark(semantic.get(q.id), 'answer_correct')} | {chose} | {quoted} | "
            f"{mark(baseline.get(q.id), 'answer_correct')} |"
        )
    lines += ["", "## Answers", ""]
    for q in questions:
        for name, outcomes in (("semantic", semantic), ("baseline", baseline)):
            outcome = outcomes.get(q.id)
            said = outcome.error if outcome and outcome.error else outcome.answer if outcome else ""
            said = " ".join(said.split())[:400]
            lines.append(f"- `{q.id}` {name}: {said}")
    errors = {o.error for o in [*semantic.values(), *baseline.values()] if o.error}
    if errors:
        lines += ["", "## Errors", ""] + [f"- {' '.join(e.split())[:300]}" for e in sorted(errors)]
    return "\n".join(lines) + "\n"


async def main(ids: list[str]) -> int:
    from semantic_agent.agent import build_agent as build_semantic
    from semantic_agent.model import DEFAULT_MODEL_ID
    from sql_baseline.agent import build_agent as build_baseline

    questions = load_questions(ids)
    database = os.environ.get("DBT_DBNAME", "dbt_dev")
    owner_url = os.environ.get(
        "WAREHOUSE_OWNER_URL", f"postgresql://warehouse:warehouse@localhost:5433/{database}"
    )
    expected = expected_numbers(questions, owner_url)
    semantic = await evaluate(
        build_semantic(),
        eval_cases(questions, expected, "semantic_agent", semantic=True),
        [ANSWER_CORRECT, METRIC_CHOICE, FRESHNESS_QUOTED],
    )
    spent = next((o for o in semantic.values() if o.skipped), None)
    if spent:
        baseline = {q.id: CaseOutcome("", {}, error=spent.error, skipped=True) for q in questions}
    else:
        baseline = await evaluate(
            build_baseline(),
            eval_cases(questions, expected, "sql_baseline", semantic=False),
            [ANSWER_CORRECT],
        )
    text = report(
        questions, expected, semantic, baseline, os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    )
    print(text)
    not_run = sum(o.skipped for o in [*semantic.values(), *baseline.values()])
    if not_run:
        reason = next(o.error for o in [*semantic.values(), *baseline.values()] if o.skipped)
        print(f"incomplete: {not_run} answers not run. {reason} {REPORT.name} left as it was.")
        return 3
    if not ids:
        REPORT.write_text(text)
        print(f"written to {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
