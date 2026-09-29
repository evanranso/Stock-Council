"""The single place the app talks to Claude."""

from __future__ import annotations

from functools import lru_cache
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from ..config import get_settings

T = TypeVar("T", bound=BaseModel)


class AgentError(RuntimeError):
    pass


@lru_cache
def client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic()


async def structured(system: str, user: str, schema: type[T], effort: str) -> T:
    """Ask Claude for a response that must validate against `schema`."""
    settings = get_settings()
    response = await client().beta.messages.parse(
        model=settings.claude_model,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
        output_config={"effort": effort},
        # If a safety classifier declines, retry on Anthropic's recommended fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise AgentError("The model declined this request.")
    if response.stop_reason == "max_tokens":
        raise AgentError("Response was cut off (max_tokens).")
    if response.parsed_output is None:
        raise AgentError("Response did not match the expected schema.")
    return response.parsed_output
