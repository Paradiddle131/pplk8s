"""The scored eval (semantic/PLAN.md SL-5): the semantic agent and the text-to-SQL baseline on the
same questions and the same model, through ADK's own eval engine (`LocalEvalService`).

`evals/questions.yaml` holds the cases: a question, or a conversation of turns in one session
(follow-ups, "how was that computed?"); each turn's expected numbers come from the warehouse when
the run starts. Five custom ADK metrics score a run, each on the turns it applies to:
- `answer_correct`: the final answer carries an expected number; for the semantic agent on a
  question no metric covers, it says the semantic layer has no such metric instead. Numbers inside
  a quoted freshness statement do not count.
- `metric_choice` (semantic agent only): its `query_metrics` calls named the expected metrics.
- `freshness_quoted` (semantic agent only, SL-4): the answer quotes every freshness statement its
  data calls returned.
- `definition_quoted`: asked how a figure was computed, the answer quotes the definition of each
  metric behind it, the metric's description in the catalog.
- `term_disambiguated`: asked with a term that means more than one metric (an `Ambiguous` glossary
  term), the answer asks which one is meant or gives every meaning's number; picking one silently
  fails.

Usage (`make agent-eval` sets the env): python -m semantic_agent.evaluation [question ids]
Writes the scores side by side to stdout and to `docs/research/semantic-agent-eval.md`. A run that
is no score prints what it got, leaves the report as it was and exits 3: the model's daily quota or
a refused key cut it short, or no question got an answer at all.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import re
import sys
from dataclasses import dataclass, field
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
# A sentence that asks the user to choose: it ends in "?" and offers or names a choice.
ASKS_WHICH = re.compile(r"[^.!?]*\b(?:which|or|mean|meant)\b[^.!?]*\?", re.IGNORECASE)
DECLINE = re.compile(
    r"no (?:such |\w+ )?metric|not (?:available|defined|covered|in the semantic layer)|"
    r"(?:does not|doesn't|do not|don't) (?:have|define|include|cover|contain)|"
    r"(?:cannot|can't|unable to) (?:answer|be answered|give|report)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Turn:
    """One user message and what its answer must carry.

    expected_sql: the number the answer carries; empty for a turn that asks for none.
    metrics: the metrics the semantic agent should query; [] with expected_sql means none covers it.
    define: "how was that computed?": the metrics whose definitions the answer quotes.
    ambiguous: the metrics a term in the question can mean; expected_sql gives one column each.
    """

    question: str
    expected_sql: str = ""
    metrics: list[str] = field(default_factory=list)
    define: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)

    @property
    def kind(self) -> str:
        return "define" if self.define else "ambiguous" if self.ambiguous else "number"


@dataclass(frozen=True)
class Question:
    """An eval case: one question, or a conversation whose turns share a session."""

    id: str
    turns: list[Turn]

    @classmethod
    def single(cls, id: str, question: str, expected_sql: str, metrics: list[str]) -> Question:
        return cls(id, [Turn(question, expected_sql, metrics)])

    @classmethod
    def from_yaml(cls, item: dict[str, Any]) -> Question:
        item = dict(item)
        case_id = item.pop("id")
        turns = item.pop("turns", None) or [item]
        return cls(case_id, [Turn(**turn) for turn in turns])

    @property
    def question(self) -> str:
        return " → ".join(t.question for t in self.turns)

    @property
    def metrics(self) -> list[str]:
        """Every metric the case names, in any role."""
        names = [n for t in self.turns for n in [*t.metrics, *t.define, *t.ambiguous]]
        return list(dict.fromkeys(names))

    @property
    def plain(self) -> bool:
        """One question that asks for one number: the main table's shape."""
        return len(self.turns) == 1 and self.turns[0].kind == "number"


# A case's expected numbers: per turn, one list per number the turn expects (a meaning of an
# ambiguous term each), every list the forms an answer may carry it in.
Expected = list[list[list[float]]]


def load_questions(ids: list[str] | None = None) -> list[Question]:
    items = yaml.safe_load(QUESTIONS.read_text())["questions"]
    questions = [Question.from_yaml(item) for item in items]
    return [q for q in questions if not ids or q.id in ids]


def expected_numbers(questions: list[Question], url: str) -> dict[str, Expected]:
    """Each turn's expected numbers from the warehouse, a rate also as a percentage."""
    found: dict[str, Expected] = {}
    with psycopg.connect(url) as conn:
        for q in questions:
            found[q.id] = []
            for turn in q.turns:
                row = conn.execute(turn.expected_sql).fetchone() if turn.expected_sql else ()  # type: ignore[arg-type]
                found[q.id].append([as_expected(float(v)) for v in row or ()])
    return found


def as_expected(value: float) -> list[float]:
    """The numbers an answer may carry for a value: a rate also as a percentage, unrounded, so an
    answer's own rounding is the only one (32.65 kept and rounded again to one decimal is 32.6)."""
    return [value, value * 100] if 0 < value < 1 else [value]


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


def _status(score: float | None) -> EvalStatus:
    if score is None:
        return EvalStatus.NOT_EVALUATED
    return EvalStatus.PASSED if score == 1.0 else EvalStatus.FAILED


def _result(scores: list[float | None], actual: list[Invocation], expected: list[Invocation]):
    """A case's result from its turns' scores; a turn the metric does not apply to scores None,
    and a case with no such turn is not evaluated."""
    per = [
        PerInvocationResult(
            actual_invocation=a, expected_invocation=e, score=s, eval_status=_status(s)
        )
        for a, e, s in zip(actual, expected, scores, strict=True)
    ]
    scored = [s for s in scores if s is not None]
    overall = sum(scored) / len(scored) if scored else None
    return EvaluationResult(
        overall_score=overall, overall_eval_status=_status(overall), per_invocation_results=per
    )


def freshness_statements(invocation: Invocation) -> list[str]:
    """The freshness statements the invocation's data calls returned, in order, whatever the data
    tool is called (#177)."""
    found = []
    for response in get_all_tool_responses(invocation.intermediate_data):
        statement = ((response.response or {}).get("freshness") or {}).get("statement")
        if statement and statement not in found:
            found.append(statement)
    return found


def _squash(text: str) -> str:
    return " ".join(text.split())


def _answer(actual: Invocation) -> str:
    """The answer's text, its quoted freshness statements left out."""
    text = _squash(_text(actual.final_response))
    for statement in freshness_statements(actual):
        text = text.replace(_squash(statement), " ")
    return text


def answer_correct(eval_metric, actual_invocations, expected_invocations, conversation_scenario):
    """1 when the answer carries the expected number, or declines where it should; a turn that
    asks for no number (a definition, an ambiguous term) is scored by its own metric."""
    scores: list[float | None] = []
    for actual, expected in zip(actual_invocations, expected_invocations or [], strict=True):
        spec, text = _spec(expected), _answer(actual)
        if spec["kind"] != "number":
            scores.append(None)
            continue
        number = spec["expected"][0]
        if spec["decline"]:
            right = bool(DECLINE.search(text)) and not carries(text, number)
        else:
            right = carries(text, number)
        scores.append(1.0 if right else 0.0)
    return _result(scores, actual_invocations, expected_invocations or [])


def _words(text: str) -> str:
    """Text as a reader compares a quotation: case, punctuation and spacing do not count."""
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.lower()).split())


def definition_quoted(eval_metric, actual_invocations, expected_invocations, conversation_scenario):
    """1 when an answer to "how was that computed?" quotes every definition it should."""
    scores: list[float | None] = []
    for actual, expected in zip(actual_invocations, expected_invocations or [], strict=True):
        definitions = _spec(expected)["define"]
        if not definitions:
            scores.append(None)
            continue
        text = _words(_text(actual.final_response))
        scores.append(1.0 if all(_words(d) in text for d in definitions.values()) else 0.0)
    return _result(scores, actual_invocations, expected_invocations or [])


def asks_or_gives_each(text: str, meanings: list[list[float]]) -> bool:
    """An answer to a question with an ambiguous term: it asks which meaning the user wants, or it
    carries every meaning's number. One number and no question is a silent pick."""
    return bool(ASKS_WHICH.search(text)) or all(carries(text, m) for m in meanings)


def term_disambiguated(
    eval_metric, actual_invocations, expected_invocations, conversation_scenario
):
    """1 when a question with an ambiguous term is answered by asking which meaning, or by all."""
    scores: list[float | None] = []
    for actual, expected in zip(actual_invocations, expected_invocations or [], strict=True):
        spec = _spec(expected)
        if spec["kind"] != "ambiguous":
            scores.append(None)
            continue
        scores.append(1.0 if asks_or_gives_each(_answer(actual), spec["expected"]) else 0.0)
    return _result(scores, actual_invocations, expected_invocations or [])


def queried_metrics(invocation: Invocation) -> set[str]:
    """The metrics the query_metrics calls named, and those of the saved queries they ran, which
    their results name."""
    named = {
        name
        for use in get_all_tool_calls(invocation.intermediate_data)
        if use.name == "query_metrics"
        for name in (use.args or {}).get("metrics") or []
    }
    saved = {
        name
        for response in get_all_tool_responses(invocation.intermediate_data)
        if response.name == "query_metrics"
        for name in (response.response or {}).get("metrics") or []
    }
    return named | saved


def metric_choice(eval_metric, actual_invocations, expected_invocations, conversation_scenario):
    """1 when the semantic agent's queries named every expected metric."""
    scores: list[float | None] = []
    for actual, expected in zip(actual_invocations, expected_invocations or [], strict=True):
        spec = _spec(expected)
        if spec["kind"] != "number":
            scores.append(None)
        else:
            scores.append(1.0 if set(spec["metrics"]) <= queried_metrics(actual) else 0.0)
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
DEFINITION_QUOTED = EvalMetric(metric_name="definition_quoted", threshold=1.0)
TERM_DISAMBIGUATED = EvalMetric(metric_name="term_disambiguated", threshold=1.0)
SEMANTIC_METRICS = [
    ANSWER_CORRECT,
    METRIC_CHOICE,
    FRESHNESS_QUOTED,
    DEFINITION_QUOTED,
    TERM_DISAMBIGUATED,
]
BASELINE_METRICS = [ANSWER_CORRECT, DEFINITION_QUOTED, TERM_DISAMBIGUATED]


def definitions(questions: list[Question]) -> dict[str, str]:
    """The catalog's description of every metric a turn asks to define: the text quoted."""
    from semantic_agent.tools import catalog

    names = {name for q in questions for t in q.turns for name in t.define}
    return {name: catalog().metric(name)["description"] for name in sorted(names)}


def eval_cases(
    questions: list[Question],
    expected: dict[str, Expected],
    app_name: str,
    semantic: bool,
    described: dict[str, str] | None = None,
) -> list[EvalCase]:
    """Each case as ADK's EvalCase: one invocation per turn, its expected final response the turn's
    spec (what the custom metrics read)."""
    described = described if described is not None else definitions(questions)
    cases = []
    for q in questions:
        conversation = []
        for turn, numbers in zip(q.turns, expected[q.id], strict=True):
            spec = {
                "kind": turn.kind,
                "expected": numbers,
                "metrics": turn.metrics,
                "decline": semantic and turn.kind == "number" and not turn.metrics,
                "define": {name: described[name] for name in turn.define},
            }
            uses = [types.FunctionCall(name="query_metrics", args={"metrics": turn.metrics})]
            conversation.append(
                Invocation(
                    user_content=types.Content(role="user", parts=[types.Part(text=turn.question)]),
                    final_response=types.Content(
                        role="model", parts=[types.Part(text=json.dumps(spec))]
                    ),
                    intermediate_data=IntermediateData(
                        tool_uses=uses if semantic and turn.metrics else []
                    ),
                )
            )
        cases.append(
            EvalCase(
                eval_id=q.id,
                conversation=conversation,
                session_input=SessionInput(app_name=app_name, user_id="eval"),
            )
        )
    return cases


@dataclass
class CaseOutcome:
    answer: str
    scores: dict[str, float | None]
    error: str | None = None
    skipped: bool = (
        False  # never sent: a failure that ends the run (ModelFailure.ends_run) came first
    )


# A rate-limited question waits out the limit once, at most this long, then runs again.
MAX_WAIT_S = 90.0


async def _wait(seconds: float) -> None:
    await asyncio.sleep(seconds)


async def evaluate(agent: LlmAgent, cases: list[EvalCase], metrics: list[EvalMetric]):
    """Runs the cases through ADK's LocalEvalService, one at a time (the free tier's rate limit).

    A case the model rate-limits waits out the limit (at most MAX_WAIT_S) and runs once more; once
    the daily quota is spent or the key refused, the cases left are skipped with that reason, never
    sent.
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
            spent = failure if failure.ends_run else None
        else:
            succeeded.append(result)
    answers = {
        r.eval_case_id: " → ".join(_text(i.final_response) for i in r.inferences or [])
        for r in succeeded
    }
    evaluate_request = EvaluateRequest(
        inference_results=succeeded,
        evaluate_config=EvaluateConfig(eval_metrics=metrics, parallelism=1),
    )
    if succeeded:
        async for result in service.evaluate(evaluate_request=evaluate_request):
            scores = {m.metric_name: m.score for m in result.overall_eval_metric_results}
            outcomes[result.eval_id] = CaseOutcome(answers.get(result.eval_id, ""), scores)
    return outcomes


ANSWER_METRICS = ("answer_correct", "definition_quoted", "term_disambiguated")


def report(questions, expected, semantic, baseline, model_id: str) -> str:
    def mark(outcome: CaseOutcome | None, metric: str) -> str:
        if outcome is None:
            return "not run"
        if outcome.skipped:
            return "skipped"
        if outcome.error:
            return "error"
        if metric in outcome.scores and outcome.scores[metric] is None:
            return "none"
        return "✓" if outcome.scores.get(metric) == 1.0 else "✗"

    def answered(outcome: CaseOutcome | None) -> str:
        """A case's answers: right when every answer metric that applies to it passed."""
        if outcome is None or outcome.skipped or outcome.error:
            return mark(outcome, "answer_correct")
        scored = [outcome.scores[m] for m in ANSWER_METRICS if outcome.scores.get(m) is not None]
        return "✓" if scored and all(score == 1.0 for score in scored) else "✗"

    plain = [q for q in questions if q.plain]
    with_metric = [q for q in plain if q.metrics]
    without = [q for q in plain if not q.metrics]
    conversations = [q for q in questions if not q.plain]

    def count(outcomes, subset, metric=None):
        return sum(
            1
            for q in subset
            if (mark(outcomes.get(q.id), metric) if metric else answered(outcomes.get(q.id))) == "✓"
        )

    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")
    lines = [
        "# Semantic agent eval",
        "",
        f"Run {stamp} by `make agent-eval` (`services/semantic-agent`, semantic/PLAN.md SL-5), "
        f"model `{model_id}`, on `dbt/dev/fixture.sql` and `dbt/dev/fixture_weeks.sql`.",
        "Each agent answers each case once through ADK's `LocalEvalService`, the turns of a "
        "conversation in one session; an answer is right when it carries the number the "
        "warehouse gives (`evals/questions.yaml`), quotes the metric's definition when asked how "
        "a figure was computed, and asks which meaning (or gives each) when a term has more than "
        "one.",
        "",
        "| | Semantic agent | Text-to-SQL baseline |",
        "|---|---|---|",
        f"| Questions a metric covers ({len(with_metric)}) | {count(semantic, with_metric)} right, "
        f"{count(semantic, with_metric, 'metric_choice')} with the expected metric, "
        f"{count(semantic, with_metric, 'freshness_quoted')} quoting their freshness | "
        f"{count(baseline, with_metric)} right |",
        f"| Questions no metric covers ({len(without)}) | {count(semantic, without)} said so | "
        f"{count(baseline, without)} right |",
    ]
    if conversations:
        lines.append(
            f"| Follow-ups, definitions and ambiguous terms ({len(conversations)}) | "
            f"{count(semantic, conversations)} right | {count(baseline, conversations)} right |"
        )
    lines += [
        f"| All ({len(questions)}) | {count(semantic, questions)} | {count(baseline, questions)} |",
        "",
        "| Question | Expected | Semantic | Metric | Freshness | Baseline |",
        "|---|---|---|---|---|---|",
    ]
    for q in plain:
        number = expected[q.id][0][0][0]
        chose = mark(semantic.get(q.id), "metric_choice") if q.metrics else "none"
        quoted = mark(semantic.get(q.id), "freshness_quoted") if q.metrics else "none"
        lines.append(
            f"| `{q.id}` {q.question} | {number:g} | "
            f"{mark(semantic.get(q.id), 'answer_correct')} | {chose} | {quoted} | "
            f"{mark(baseline.get(q.id), 'answer_correct')} |"
        )
    if conversations:
        lines += [
            "",
            "A conversation runs its turns in one session; a column no turn of a case applies to "
            "says none.",
            "",
            "| Case | Expected | Semantic: numbers | Definition | Asks which | Metric | Freshness "
            "| Baseline: numbers | Definition | Asks which |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for q in conversations:
            numbers = " → ".join(
                " / ".join(f"{n[0]:g}" for n in turn) or "–" for turn in expected[q.id]
            )
            s, b = semantic.get(q.id), baseline.get(q.id)
            lines.append(
                f"| `{q.id}` {q.question} | {numbers} | "
                + " | ".join(
                    mark(s, m) for m in (*ANSWER_METRICS, "metric_choice", "freshness_quoted")
                )
                + " | "
                + " | ".join(mark(b, m) for m in ANSWER_METRICS)
                + " |"
            )
    lines += ["", "## Answers", ""]
    for q in questions:
        for name, outcomes in (("semantic", semantic), ("baseline", baseline)):
            outcome = outcomes.get(q.id)
            said = outcome.error if outcome and outcome.error else outcome.answer if outcome else ""
            said = " ".join(said.split())[: 400 * len(q.turns)]
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
        SEMANTIC_METRICS,
    )
    spent = next((o for o in semantic.values() if o.skipped), None)
    if spent:
        baseline = {q.id: CaseOutcome("", {}, error=spent.error, skipped=True) for q in questions}
    else:
        baseline = await evaluate(
            build_baseline(),
            eval_cases(questions, expected, "sql_baseline", semantic=False),
            BASELINE_METRICS,
        )
    text = report(
        questions, expected, semantic, baseline, os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    )
    print(text)
    outcomes = [*semantic.values(), *baseline.values()]
    not_run = sum(o.skipped for o in outcomes)
    if not_run:
        reason = next(o.error for o in outcomes if o.skipped)
        print(f"incomplete: {not_run} answers not run. {reason} {REPORT.name} left as it was.")
        return 3
    if outcomes and all(o.error for o in outcomes):
        reasons = " ".join(sorted({o.error or "" for o in outcomes}))
        print(f"no answers: every model call failed. {reasons} {REPORT.name} left as it was.")
        return 3
    if not ids:
        REPORT.write_text(text)
        print(f"written to {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
