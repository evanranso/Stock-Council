"""The council's scoring formula.

Hybrid design:
  1. Each specialist gives a lean + conviction (0-100) for weeks, months, years.
  2. This module turns those into a -100..+100 score per horizon using a weight
     table (which data matters for which horizon) and data quality.
  3. The challenger's objections and echo-chamber findings cut weights.
  4. The judge may nudge each horizon by at most MAX_JUDGE_ADJUSTMENT points,
     with a written reason. Ratings are derived from the final numbers here,
     never picked freely by a model.

All the tunable numbers live at the top of this file. They are starting
guesses; the verdict history (see cache.record_verdict) is what they should
eventually be calibrated against.
"""

from __future__ import annotations

import math

from .schemas import (
    HORIZONS,
    AnalystReport,
    ChallengeReport,
    Contribution,
    Horizon,
    HorizonScore,
    HorizonVerdict,
    JudgeRuling,
    Lean,
    Rating,
    Verdict,
)

# How much each analyst's view counts for each horizon (0-1).
WEIGHTS: dict[str, dict[Horizon, float]] = {
    "price": {"weeks": 1.0, "months": 0.6, "years": 0.2},
    "financials": {"weeks": 0.2, "months": 0.7, "years": 1.0},
    "analysts": {"weeks": 0.4, "months": 0.6, "years": 0.4},
    "earnings": {"weeks": 0.6, "months": 1.0, "years": 0.6},
    "insiders": {"weeks": 0.3, "months": 0.6, "years": 0.5},
    "congress": {"weeks": 0.2, "months": 0.3, "years": 0.2},
    "news": {"weeks": 0.8, "months": 0.5, "years": 0.2},
    "filings": {"weeks": 0.2, "months": 0.6, "years": 0.9},
    "institutions": {"weeks": 0.3, "months": 0.5, "years": 0.5},
    "options": {"weeks": 1.0, "months": 0.4, "years": 0.1},
    "economy": {"weeks": 0.3, "months": 0.6, "years": 0.6},
    "related": {"weeks": 0.7, "months": 0.6, "years": 0.3},
}

DATA_QUALITY = {"good": 1.0, "partial": 0.6, "poor": 0.3}

# Challenger objections multiply the affected analyst's weight.
SEVERITY_PENALTY = {"low": 1.0, "medium": 0.8, "high": 0.5}
MIN_PENALTY_FACTOR = 0.25  # stacked objections can't erase an analyst entirely

# A phantom neutral analyst with this much weight. With thin evidence it pulls
# the score toward 0, so one confident analyst alone can't produce +90.
NEUTRAL_PRIOR_WEIGHT = 1.0

# Each horizon is rated on its own; the person picks the timeframe they care about.
# Calibration (Oct 2026, first 8 live runs): horizon scores ranged -12..+23, because every
# score is an average over many analysts after the neutral prior, challenger penalties and
# echo-chamber collapsing. At the old +-20 only 1 of 24 horizon scores cleared the bar; at
# +-10 the spread looked realistic (months: 4 Buy, 4 Hold). Revisit as verdict history grows.
LEAN_THRESHOLD = 10  # |score| below this is neutral / Hold
STRONG_THRESHOLD = 30

# The judge's nudge stays below the Hold/Buy line so it can't create a call on its own.
MAX_JUDGE_ADJUSTMENT = 8

# Legacy blended score across horizons (kept for older clients and the verdict history).
HORIZON_BLEND: dict[Horizon, float] = {"weeks": 0.2, "months": 0.4, "years": 0.4}

DIRECTION: dict[Lean, int] = {"bullish": 1, "bearish": -1, "neutral": 0}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def lean_for(score: float) -> Lean:
    if score >= LEAN_THRESHOLD:
        return "bullish"
    if score <= -LEAN_THRESHOLD:
        return "bearish"
    return "neutral"


def rating_for(score: float) -> Rating:
    if score >= STRONG_THRESHOLD:
        return "strong_buy"
    if score >= LEAN_THRESHOLD:
        return "buy"
    if score <= -STRONG_THRESHOLD:
        return "strong_sell"
    if score <= -LEAN_THRESHOLD:
        return "sell"
    return "hold"


def score_horizon(
    horizon: Horizon, reports: list[AnalystReport], challenge: ChallengeReport | None = None
) -> HorizonScore:
    """Weighted, penalty-adjusted average of the analysts' signed convictions for one horizon."""
    rows: dict[str, dict] = {}
    for r in reports:
        if r.opinion is None or r.analyst_id not in WEIGHTS:
            continue
        view = r.opinion.outlook.model_dump()[horizon]
        rows[r.analyst_id] = {
            "lean": view["lean"],
            "conviction": int(_clamp(view["conviction"], 0, 100)),
            "weight": WEIGHTS[r.analyst_id][horizon] * DATA_QUALITY[r.opinion.data_quality],
            "penalty": 1.0,
            "notes": [],
        }

    if challenge is not None:
        for obj in challenge.objections:
            if horizon not in obj.horizons:
                continue
            for aid in obj.affected_analysts:
                if aid in rows and SEVERITY_PENALTY[obj.severity] < 1:
                    rows[aid]["penalty"] *= SEVERITY_PENALTY[obj.severity]
                    rows[aid]["notes"].append(f"{obj.severity} objection: {obj.objection[:140]}")
        for row in rows.values():
            row["weight"] *= max(row["penalty"], MIN_PENALTY_FACTOR)

        # Echo chambers: analysts leaning on one shared fact count as one analyst, not several.
        for group in challenge.shared_evidence:
            members = [rows[a] for a in dict.fromkeys(group.analyst_ids) if a in rows]
            total = sum(m["weight"] for m in members)
            if len(members) < 2 or total == 0:
                continue
            factor = max(m["weight"] for m in members) / total
            for m in members:
                m["weight"] *= factor
                m["notes"].append(f"shares one fact with {len(members) - 1} other analyst(s): {group.fact[:100]}")

    numerator = 0.0
    denominator = NEUTRAL_PRIOR_WEIGHT
    directional_abs = 0.0
    for row in rows.values():
        d, c, w = DIRECTION[row["lean"]], row["conviction"], row["weight"]
        numerator += w * d * c
        directional_abs += w * abs(d) * c
        # A neutral only counts as much as its conviction; "my data doesn't cover this" (0) drops out.
        denominator += w if d else w * c / 100
    score = numerator / denominator

    # Evidence: usable weight present vs. what a full, clean council would supply.
    full = sum(w[horizon] for w in WEIGHTS.values())
    present = sum(row["weight"] * (1 if DIRECTION[row["lean"]] else row["conviction"] / 100) for row in rows.values())
    evidence = _clamp(present / full, 0, 1)
    agreement = abs(numerator) / directional_abs if directional_abs else 1.0
    confidence = round(100 * math.sqrt(evidence) * (0.3 + 0.7 * agreement))

    contributions = [
        Contribution(
            analyst_id=aid,
            lean=row["lean"],
            conviction=row["conviction"],
            weight=round(row["weight"], 3),
            points=round(row["weight"] * DIRECTION[row["lean"]] * row["conviction"] / denominator, 1),
            penalties=row["notes"],
        )
        for aid, row in rows.items()
    ]
    contributions.sort(key=lambda c: -abs(c.points))
    return HorizonScore(
        horizon=horizon,
        score=round(score, 1),
        confidence=confidence,
        evidence=round(evidence, 3),
        agreement=round(agreement, 3),
        contributions=contributions,
    )


def score_all(reports: list[AnalystReport], challenge: ChallengeReport | None = None) -> dict[Horizon, HorizonScore]:
    return {h: score_horizon(h, reports, challenge) for h in HORIZONS}


def assemble_verdict(scores: dict[Horizon, HorizonScore], ruling: JudgeRuling) -> Verdict:
    """Apply the judge's bounded adjustments and derive leans and the rating from the numbers."""
    horizons: dict[Horizon, HorizonVerdict] = {}
    for h in HORIZONS:
        s, r = scores[h], getattr(ruling, h)
        adj = int(_clamp(r.adjustment, -MAX_JUDGE_ADJUSTMENT, MAX_JUDGE_ADJUSTMENT))
        final = round(_clamp(s.score + adj, -100, 100), 1)
        horizons[h] = HorizonVerdict(
            lean=lean_for(final),
            rating=rating_for(final),
            score=final,
            formula_score=s.score,
            adjustment=adj,
            adjustment_reason=r.adjustment_reason,
            confidence=s.confidence,
            rationale=r.rationale,
            scoring=s,
        )

    overall = round(sum(HORIZON_BLEND[h] * horizons[h].score for h in HORIZONS), 1)
    confidence = round(sum(HORIZON_BLEND[h] * horizons[h].confidence for h in HORIZONS))
    return Verdict(
        rating=rating_for(overall),
        score=overall,
        confidence=confidence,
        bottom_line=ruling.bottom_line,
        reasons_for=ruling.reasons_for,
        reasons_against=ruling.reasons_against,
        summary=ruling.summary,
        key_catalysts=ruling.key_catalysts,
        key_risks=ruling.key_risks,
        dissenting_analysts=ruling.dissenting_analysts,
        what_would_change_the_verdict=ruling.what_would_change_the_verdict,
        **horizons,
    )
