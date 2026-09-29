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


Horizon = Literal["weeks", "months", "years"]
HORIZONS: tuple[Horizon, ...] = ("weeks", "months", "years")


class HorizonView(BaseModel):
    lean: Lean
    conviction: int = Field(
        description=(
            "0-100 strength of evidence for this lean over this horizon. For a neutral lean: high means the data "
            "clearly says 'no edge', 0 means your data doesn't speak to this horizon at all."
        )
    )
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
    affected_analysts: list[str] = Field(
        description=(
            "analyst_ids whose horizon views this objection undermines. Empty if it only hits an advocate's framing."
        )
    )
    horizons: list[Horizon] = Field(description="Which horizons the objection applies to.")


class SharedEvidence(BaseModel):
    fact: str = Field(description="The single underlying fact several analysts are all reacting to.")
    analyst_ids: list[str] = Field(description="The analysts whose views all rest on that fact (2 or more).")


class ChallengeReport(BaseModel):
    objections: list[Objection]
    leans_that_hold_up: list[str] = Field(description="Claims that survived scrutiny.")
    shared_evidence: list[SharedEvidence] = Field(
        description="Echo chambers: groups of analysts counting the same underlying fact. Empty if none."
    )
    net_assessment: str


# ---------------------------------------------------------------------------
# Scoring (computed in code, see scoring.py)
# ---------------------------------------------------------------------------


class Contribution(BaseModel):
    analyst_id: str
    lean: Lean
    conviction: int
    weight: float = Field(description="Horizon weight x data quality, after challenger penalties.")
    points: float = Field(description="This analyst's share of the horizon score; all points sum to the score.")
    penalties: list[str] = Field(default_factory=list)


class HorizonScore(BaseModel):
    horizon: Horizon
    score: float = Field(description="-100 (strongly bearish) to +100 (strongly bullish).")
    confidence: int
    evidence: float = Field(description="0-1: how much of the council's usual evidence was present and usable.")
    agreement: float = Field(description="0-1: how much the directional analysts agree with each other.")
    contributions: list[Contribution]


# ---------------------------------------------------------------------------
# Stage 4: the judge rules on the formula; the final verdict is assembled in code
# ---------------------------------------------------------------------------


class HorizonRuling(BaseModel):
    adjustment: int = Field(
        description="Points to add to the formula score (negative = more bearish). 0 if the formula got it right."
    )
    adjustment_reason: str = Field(description="Why the adjustment; say 'Formula stands.' if 0.")
    rationale: str = Field(description="Plain-English outlook for this horizon.")


class JudgeRuling(BaseModel):
    summary: str = Field(description="3-5 sentence plain-English verdict.")
    weeks: HorizonRuling
    months: HorizonRuling
    years: HorizonRuling
    key_catalysts: list[str]
    key_risks: list[str]
    dissenting_analysts: list[str] = Field(description="analyst_id: short reason the verdict goes against them.")
    what_would_change_the_verdict: str


Rating = Literal["strong_buy", "buy", "hold", "sell", "strong_sell"]


class HorizonVerdict(BaseModel):
    lean: Lean
    score: float = Field(description="Final score: formula score + judge adjustment, -100..100.")
    formula_score: float
    adjustment: int
    adjustment_reason: str
    confidence: int
    rationale: str
    scoring: HorizonScore


class Verdict(BaseModel):
    rating: Rating
    score: float = Field(description="Horizon-weighted blend of the final horizon scores.")
    confidence: int
    summary: str
    weeks: HorizonVerdict
    months: HorizonVerdict
    years: HorizonVerdict
    key_catalysts: list[str]
    key_risks: list[str]
    dissenting_analysts: list[str]
    what_would_change_the_verdict: str


class CouncilRun(BaseModel):
    ticker: str
    company_name: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    model: str
    reference_price: float | None = Field(default=None, description="Last close when the council ran.")
    analysts: list[AnalystReport] = Field(default_factory=list)
    bull: CaseReport | None = None
    bear: CaseReport | None = None
    challenge: ChallengeReport | None = None
    verdict: Verdict | None = None
