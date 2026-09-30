"""Analysis depth: which models and effort each tier uses, and what it costs in credits.

Deep uses the configured CLAUDE_MODEL / SPECIALIST_EFFORT / DEBATE_EFFORT, so it's
exactly the original council. Quick and Standard trade some nuance for cost by
running the 10 analysts (most of the calls) on a cheaper model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .config import get_settings

CHEAP_MODEL = os.getenv("CHEAP_MODEL", "claude-sonnet-5-5")


@dataclass(frozen=True)
class Depth:
    id: str
    label: str
    rank: int  # higher = deeper; a cached run of equal or higher rank can stand in for a request
    analyst_model: str
    analyst_effort: str
    debate_model: str
    debate_effort: str
    credits: int
    blurb: str

    def public(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "credits": self.credits,
            "blurb": self.blurb,
            "analyst_model": self.analyst_model,
            "debate_model": self.debate_model,
        }


def _profiles() -> dict[str, Depth]:
    s = get_settings()
    return {
        "quick": Depth(
            "quick",
            "Quick",
            0,
            CHEAP_MODEL,
            "low",
            CHEAP_MODEL,
            "medium",
            int(os.getenv("CREDITS_QUICK", "1")),
            "A fast first read. Same 12 data sources and debate, with a lighter model throughout.",
        ),
        "standard": Depth(
            "standard",
            "Standard",
            1,
            CHEAP_MODEL,
            "medium",
            s.claude_model,
            s.debate_effort,
            int(os.getenv("CREDITS_STANDARD", "2")),
            "Analysts on a lighter model; the debate, challenger and judge on the most capable one.",
        ),
        "deep": Depth(
            "deep",
            "Deep",
            2,
            s.claude_model,
            s.specialist_effort,
            s.claude_model,
            s.debate_effort,
            int(os.getenv("CREDITS_DEEP", "3")),
            "The most capable model for every agent. The most nuanced read.",
        ),
    }


DEFAULT_DEPTH = "standard"


def get_depth(depth_id: str | None) -> Depth:
    profiles = _profiles()
    return profiles.get((depth_id or DEFAULT_DEPTH).lower(), profiles[DEFAULT_DEPTH])


def all_depths() -> list[Depth]:
    return list(_profiles().values())
