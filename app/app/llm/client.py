"""LiteLLM wrapper.

LiteLLM lets us swap Claude / OpenAI / DashScope (Qwen) / 文心 by changing
the `model` string only (with provider prefix like `dashscope/qwen-plus`).
The user's API keys are picked up automatically from env vars when LiteLLM
sees the matching provider prefix, but we also accept explicit values from
our Settings (.env file).
"""
from __future__ import annotations

import os
from typing import AsyncIterator, Iterable

import litellm

from app.config import settings


# Push API keys into the process env so LiteLLM picks them up by convention.
def _bootstrap_keys() -> None:
    if settings.dashscope_api_key and not os.getenv("DASHSCOPE_API_KEY"):
        os.environ["DASHSCOPE_API_KEY"] = settings.dashscope_api_key
    if settings.anthropic_api_key and not os.getenv("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.openai_api_key and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key


_bootstrap_keys()


# Avoid LiteLLM's debug logging spam.
litellm.suppress_debug_info = True


def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    response_format: dict | None = None,
) -> str:
    """Non-streaming completion. Returns the text content."""
    resp = litellm.completion(
        model=model or settings.llm_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
    return resp.choices[0].message.content or ""


def chat_stream(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 2048,
) -> Iterable[str]:
    """Synchronous streaming generator. Yields content deltas (strings)."""
    stream = litellm.completion(
        model=model or settings.llm_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta.content
        except (IndexError, AttributeError):
            delta = None
        if delta:
            yield delta


def embed(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    """Embed a batch of texts. Returns list of float vectors."""
    if not texts:
        return []
    resp = litellm.embedding(
        model=model or settings.embedding_model,
        input=texts,
    )
    return [d["embedding"] for d in resp.data]
