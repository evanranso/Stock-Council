"""Shared data shapes: what data adapters produce and what each agent must return.

Agent output models are passed to Claude as structured-output schemas, so every
report comes back in a predictable, UI-renderable shape.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Lean = Literal["bullish", "bearish", "neutral"]
PacketStatus = Literal["ok", "partial", "unavailable"]


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------


class DataPacket(BaseModel):
    """Everything one specialist is allowed to see. Nothing else."""

    segment: str
    ticker: str
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: PacketStatus = "ok"
    sources: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage 1: specialists
# ---------------------------------------------------------------------------


class HorizonView(BaseModel):
    lean: Lean
    rationale: str = Field(description="One or two sentences grounded in the data.")


class Outlook(BaseModel):
    weeks: HorizonView = Field(description="Next 1-4 weeks.")
    months: HorizonView = Field(description="Next 1-6 months.")
    years: HorizonView = Field(description="Next 1-3 years.")


class Finding(BaseModel):
    point: str = Field(description="The observation, stated plainly.")
    evidence: str = Field(description="The specific numbers/dates from the data that support it.")
    implication: Lean


class AnalystOpinion(BaseModel):
    """What a specialist returns. The model fills this in from its packet only."""

    stance: Lean
    conviction: int = Field(description="0-100. How strongly the data supports the stance.")
    headline: str = Field(description="One-sentence takeaway.")
    key_findings: list[Finding] = Field(description="3-6 findings, most important first.")
    risks_to_view: list[str] = Field(description="What in this data argues against the stance.")
    what_would_change_my_mind: str
    data_quality: Literal["good", "partial", "poor"]
    outlook: Outlook


class AnalystReport(BaseModel):
    analyst_id: str
    analyst_name: str
    packet_status: PacketStatus
    opinion: AnalystOpinion | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Stage 2-4: debate
# ---------------------------------------------------------------------------


class Argument(BaseModel):
    claim: str
    supporting_analysts: list[str] = Field(description="analyst_ids whose reports back this claim.")
    evidence: str


class CaseReport(BaseModel):
    """Bull or bear advocate output."""

    thesis: str
    arguments: list[Argument] = Field(description="3-6 arguments, strongest first.")
    catalysts: list[str] = Field(description="Events that would prove this case right.")
    weakest_point: str = Field(description="The most honest admission of where this case is thin.")


class Objection(BaseModel):
    target: str = Field(description="'bull', 'bear', or an analyst_id.")
    claim_challenged: str
    objection: str
    severity: Literal["low", "medium", "high"]


class ChallengeReport(BaseModel):
    objections: list[Objection]
    leans_that_hold_up: list[str] = Field(description="Claims that survived scrutiny.")
    echo_chamber_check: str = Field(
        description="Are multiple analysts leaning on the same underlying fact? Name it if so."
    )
    net_assessment: str


class HorizonVerdict(BaseModel):
    lean: Lean
    confidence: int = Field(description="0-100.")
    rationale: str


class Verdict(BaseModel):
    rating: Literal["strong_buy", "buy", "hold", "sell", "strong_sell"]
    confidence: int = Field(description="0-100 overall confidence in the rating.")
    summary: str = Field(description="3-5 sentence plain-English verdict.")
    weeks: HorizonVerdict
    months: HorizonVerdict
    years: HorizonVerdict
    key_catalysts: list[str]
    key_risks: list[str]
    dissenting_analysts: list[str] = Field(description="analyst_ids whose view the verdict goes against, and why.")
    what_would_change_the_verdict: str


class CouncilRun(BaseModel):
    ticker: str
    company_name: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    model: str
    analysts: list[AnalystReport] = Field(default_factory=list)
    bull: CaseReport | None = None
    bear: CaseReport | None = None
    challenge: ChallengeReport | None = None
    verdict: Verdict | None = None
