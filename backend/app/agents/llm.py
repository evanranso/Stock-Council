"""The single place the app talks to Claude."""

from __future__ import annotations

from functools import lru_cache
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from .. import usage
from ..config import get_settings

T = TypeVar("T", bound=BaseModel)


class AgentError(RuntimeError):
    pass


@lru_cache
def client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic()


async def structured(
    system: str, user: str, schema: type[T], effort: str, label: str = "agent", model: str | None = None
) -> T:
    """Ask Claude for a response that must validate against `schema`. `label` names the agent in cost logs."""
    settings = get_settings()
    model = model or settings.claude_model
    response = await client().beta.messages.parse(
        model=model,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
        output_config={"effort": effort},
        # If a safety classifier declines, retry on Anthropic's recommended fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    # Priced by the model that actually served the call (a refusal fallback can differ).
    usage.record(label, response.model or model, response.usage)
    if response.stop_reason == "refusal":
        raise AgentError("The model declined this request.")
    if response.stop_reason == "max_tokens":
        raise AgentError("Response was cut off (max_tokens).")
    if response.parsed_output is None:
        raise AgentError("Response did not match the expected schema.")
    return response.parsed_output
