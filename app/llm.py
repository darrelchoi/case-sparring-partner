"""gpt-6-luna through Portkey, the same setup as hw6."""

from __future__ import annotations

import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import MODEL_NAME, ROOT

# The .env file is looked for in the repo folder first, then one folder up (how the teaching staff run it).
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

_model: OpenAIResponsesModel | None = None


def build_model() -> OpenAIResponsesModel:
    global _model
    if _model is not None:
        return _model
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError(
            "PORTKEY_API_KEY is not set. Put a .env file with PORTKEY_API_KEY=... in this folder or the folder above it."
        )
    client = AsyncOpenAI(
        base_url=PORTKEY_BASE_URL,
        api_key=api_key,
        timeout=120,
        max_retries=2,
        default_headers={
            "x-portkey-provider": "openai",
            # The course gateway can replay whole cached responses; force a real model call every time
            # so token counts are honest.
            "x-portkey-cache-force-refresh": "true",
        },
    )
    _model = OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    return _model


def settings(cache_key: str, effort: str = "low", max_tokens: int = 4_000) -> OpenAIResponsesModelSettings:
    """Cache-friendly settings: static instructions are cached, and one cache key per conversation keeps
    follow-up requests on the server that already holds the prefix."""
    return OpenAIResponsesModelSettings(
        max_tokens=max_tokens,
        openai_reasoning_effort=effort,
        openai_prompt_cache_options={"mode": "implicit", "ttl": "30m"},
        openai_cache_instructions=True,
        openai_prompt_cache_key=cache_key,
    )
