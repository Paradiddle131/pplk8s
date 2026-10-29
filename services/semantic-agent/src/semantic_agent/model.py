"""Model factory: the only place that names a model provider (semantic/PLAN.md SL-2).

`MODEL_BACKEND` and `MODEL_ID` pick the model; agent code calls `build_model()` and never branches.
The lab runs OpenRouter's free tier; work runs Gemini. Each request is bounded by
`MODEL_TIMEOUT_S` and retried `MODEL_RETRIES` times.
"""

from __future__ import annotations

import os

from google.adk.models.base_llm import BaseLlm

BACKENDS = ("openrouter", "gemini")
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
    timeout = float(os.environ.get("MODEL_TIMEOUT_S", "120"))
    retries = int(os.environ.get("MODEL_RETRIES", "2"))

    if backend == "openrouter":
        from google.adk.models.lite_llm import LiteLlm

        # The key comes from OPENROUTER_API_KEY, or a cloud network secret that replaces it in
        # flight (the proxy then needs only a placeholder).
        os.environ.setdefault("OPENROUTER_API_KEY", "placeholder-replaced-by-the-proxy")
        return LiteLlm(model=f"openrouter/{model_id}", timeout=timeout, num_retries=retries)

    from google.adk.models.google_llm import Gemini
    from google.genai import types

    return Gemini(
        model=model_id,
        retry_options=types.HttpRetryOptions(attempts=retries + 1, http_status_codes=[429, 503]),
        client_kwargs={"http_options": types.HttpOptions(timeout=int(timeout * 1000))},
    )
