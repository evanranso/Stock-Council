"""Token and dollar accounting for every Claude call in a council run.

A Tracker is attached to the running council through a context variable, so
every call made while the run is going (including the parallel specialist
tasks, which inherit the context) is recorded against that run.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

# USD per million tokens: (input, output). Cache reads bill at 0.1x input, cache writes at 1.25x.
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-fable-5-1": (10.0, 50.0),
}
DEFAULT_PRICE = PRICES["claude-opus-5-5"]


def price_for(model: str) -> tuple[float, float]:
    if model in PRICES:
        return PRICES[model]
    # Tolerate suffixed ids (e.g. dated or platform-prefixed variants).
    for name, price in sorted(PRICES.items(), key=lambda kv: -len(kv[0])):
        if name in model:
            return price
    return DEFAULT_PRICE


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float:
    inp, out = price_for(model)
    return (input_tokens * inp + output_tokens * out + cache_read * inp * 0.1 + cache_write * inp * 1.25) / 1_000_000


@dataclass
class Tracker:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def add(self, agent: str, model: str, usage: Any) -> None:
        inp = getattr(usage, "input_tokens", 0) or 0
        out = getattr(usage, "output_tokens", 0) or 0
        cr = getattr(usage, "cache_read_input_tokens", 0) or 0
        cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.calls.append(
            {
                "agent": agent,
                "model": model,
                "input_tokens": inp,
                "output_tokens": out,
                "cache_read_tokens": cr,
                "cost_usd": round(cost_usd(model, inp, out, cr, cw), 5),
            }
        )

    def summary(self) -> dict[str, Any]:
        return {
            "calls": len(self.calls),
            "input_tokens": sum(c["input_tokens"] for c in self.calls),
            "output_tokens": sum(c["output_tokens"] for c in self.calls),
            "cost_usd": round(sum(c["cost_usd"] for c in self.calls), 4),
            "by_agent": self.calls,
        }


_current: ContextVar[Tracker | None] = ContextVar("council_usage", default=None)


def start() -> Tracker:
    tracker = Tracker()
    _current.set(tracker)
    return tracker


def current() -> Tracker | None:
    return _current.get()


def record(agent: str, model: str, usage: Any) -> None:
    tracker = _current.get()
    if tracker is not None:
        tracker.add(agent, model, usage)
