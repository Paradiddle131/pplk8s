"""Model factory: the only place that names a model provider (semantic/PLAN.md SL-2).

`MODEL_BACKEND` and `MODEL_ID` pick the model; agent code calls `build_model()` and
`request_config()` and never branches. The lab runs OpenRouter's free tier; work runs Gemini. Each
request is bounded by `MODEL_TIMEOUT_S` and retried `MODEL_RETRIES` times.

A model call that still fails (a spent free-tier quota, per minute or per day, included) ends the
turn with an answer that says so, through ADK's `on_model_error_callback`: `answer_model_failure`
on every agent. The event carries the failure in `custom_metadata["model_failure"]`, which is how
the eval tells a spent quota from a wrong answer.
"""

from __future__ import annotations

import dataclasses
import datetime
import os
import re
import time
from typing import Any, Literal

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

BACKENDS = ("openrouter", "gemini")
FAILURE_KEY = "model_failure"
# OpenRouter states its reset in the body (epoch ms), Gemini its retry delay ("40s").
RESET_MS = re.compile(r"X-RateLimit-Reset[\"']?:\s*[\"']?(\d{12,})", re.IGNORECASE)
RETRY_DELAY = re.compile(r"retryDelay[\"']?:\s*[\"']?(\d+(?:\.\d+)?)s", re.IGNORECASE)
PER_DAY = re.compile(r"per-day|PerDay", re.IGNORECASE)
DEFAULT_MODEL_ID = "nvidia/nemotron-3.5-super-vl:free"


def build_model(backend: str | None = None, model_id: str | None = None) -> BaseLlm:
    if backend is None:
        backend = os.environ.get("MODEL_BACKEND", "openrouter")
    if model_id is None:
        model_id = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    if backend not in BACKENDS:
        raise ValueError(f"MODEL_BACKEND must be one of {BACKENDS}, got {backend!r}")
    if not model_id:
        raise ValueError("MODEL_ID is empty")
    # OpenRouter's free tier only, whatever the key's budget allows: a spent free quota waits for
    # its reset, it never falls back to a paid model.
    if backend == "openrouter" and not model_id.endswith(":free"):
        raise ValueError(f"OpenRouter models must be free (an id ending ':free'), got {model_id!r}")
    timeout = float(os.environ.get("MODEL_TIMEOUT_S", "120"))
    retries = int(os.environ.get("MODEL_RETRIES", "2"))

    if backend == "openrouter":
        from google.adk.models.lite_llm import LiteLlm

        # The key comes from OPENROUTER_API_KEY, or a cloud network secret that replaces it in
        # flight (the proxy then needs only a placeholder).
        os.environ.setdefault("OPENROUTER_API_KEY", "placeholder-replaced-by-the-proxy")
        return LiteLlm(model=f"openrouter/{model_id}", timeout=timeout, num_retries=retries)

    from google.adk.models.google_llm import Gemini

    return Gemini(
        model=model_id,
        retry_options=types.HttpRetryOptions(attempts=retries + 1, http_status_codes=[429, 503]),
        client_kwargs={"http_options": types.HttpOptions(timeout=int(timeout * 1000))},
    )


def request_config(backend: str | None = None) -> types.GenerateContentConfig:
    """Every agent's request config: it carries the `MODEL_RETRIES` retries with each request.

    ADK's eval engine gives a request without retry options its own (7 attempts, through
    `EnsureRetryOptionsPlugin`), which ADK's LiteLlm turns into LiteLLM's `num_retries` (#116).
    LiteLlm reads `attempts` as retries after the first call; google-genai as all calls.
    """
    if backend is None:
        backend = os.environ.get("MODEL_BACKEND", "openrouter")
    retries = int(os.environ.get("MODEL_RETRIES", "2"))
    attempts = retries if backend == "openrouter" else retries + 1
    retry = types.HttpRetryOptions(attempts=attempts, http_status_codes=[429, 503])
    return types.GenerateContentConfig(http_options=types.HttpOptions(retry_options=retry))


@dataclasses.dataclass(frozen=True)
class ModelFailure:
    """A model call that failed after its retries.

    `daily_quota`: the free tier's requests for the day are spent; `auth`: the provider refused the
    credentials (401 or 403), so no later call can succeed either; `rate_limit`: a per-minute or
    upstream limit, worth one retry after `retry_after_s`; `error`: anything else.
    """

    kind: Literal["daily_quota", "auth", "rate_limit", "error"]
    message: str
    retry_after_s: float | None = None

    @property
    def ends_run(self) -> bool:
        """No call after this one can succeed until someone acts: stop sending."""
        return self.kind in ("daily_quota", "auth")

    def answer(self) -> str:
        if self.kind == "daily_quota":
            resets = ""
            if self.retry_after_s is not None:
                at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
                    seconds=self.retry_after_s
                )
                resets = f" It resets at {at:%Y-%m-%dT%H:%MZ}."
            return f"No answer: the model's daily request quota is spent.{resets}"
        if self.kind == "rate_limit":
            wait = f"{self.retry_after_s:.0f} s" if self.retry_after_s is not None else "a minute"
            return f"No answer: the model is rate-limited right now; ask again in {wait}."
        if self.kind == "auth":
            return (
                "No answer: the model provider refused the credentials; check the API key "
                f"(OPENROUTER_API_KEY for OpenRouter) ({self.message[:200]})."
            )
        return f"No answer: the model call failed ({self.message[:200]})."


def classify(error: BaseException) -> ModelFailure:
    """Reads a provider error (LiteLLM's or google-genai's) into a ModelFailure."""
    text = str(error)
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status in (401, 403):
        return ModelFailure("auth", " ".join(text.split())[:500])
    if status != 429 and "RESOURCE_EXHAUSTED" not in text:
        return ModelFailure("error", " ".join(text.split())[:500])
    retry_after = None
    if reset := RESET_MS.search(text):
        retry_after = max(0.0, int(reset[1]) / 1000 - time.time())
    elif delay := RETRY_DELAY.search(text):
        retry_after = float(delay[1])
    kind = "daily_quota" if PER_DAY.search(text) else "rate_limit"
    return ModelFailure(kind, " ".join(text.split())[:500], retry_after)


def answer_model_failure(
    callback_context: CallbackContext, llm_request: LlmRequest, error: Exception
) -> LlmResponse:
    """ADK's on_model_error_callback: the turn ends with an answer naming the failure, never an
    exception out of the runner."""
    failure = classify(error)
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=failure.answer())]),
        error_code=failure.kind.upper(),
        error_message=failure.message,
        custom_metadata={FAILURE_KEY: dataclasses.asdict(failure)},
    )


def failure_of(events: list[Any]) -> ModelFailure | None:
    """The model failure a turn's events carry, if any."""
    for event in events:
        if found := (event.custom_metadata or {}).get(FAILURE_KEY):
            return ModelFailure(**found)
    return None
