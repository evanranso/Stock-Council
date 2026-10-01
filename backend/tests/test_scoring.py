import pytest

from app import scoring
from app.schemas import (
    AnalystOpinion,
    AnalystReport,
    ChallengeReport,
    Finding,
    HorizonRuling,
    HorizonView,
    JudgeRuling,
    Objection,
    Outlook,
    SharedEvidence,
)


def report(aid, lean="bullish", conviction=60, quality="good", horizons=None):
    views = {h: HorizonView(lean=lean, conviction=conviction, rationale="r") for h in ("weeks", "months", "years")}
    views.update(horizons or {})
    op = AnalystOpinion(
        stance=lean,
        conviction=conviction,
        headline="h",
        key_findings=[Finding(point="p", evidence="e", implication=lean)],
        risks_to_view=[],
        what_would_change_my_mind="m",
        data_quality=quality,
        outlook=Outlook(**views),
    )
    return AnalystReport(analyst_id=aid, analyst_name=aid, packet_status="ok", opinion=op)


def challenge(objections=(), shared=()):
    return ChallengeReport(
        objections=list(objections),
        leans_that_hold_up=[],
        shared_evidence=list(shared),
        net_assessment="n",
        headline="h",
    )


def test_neutral_prior_keeps_one_analyst_from_producing_an_extreme_score():
    s = scoring.score_horizon("years", [report("financials", conviction=90)])
    # weight 1.0, conviction 90, plus a 1.0 neutral prior -> 90 / 2 = 45
    assert s.score == pytest.approx(45.0)
    assert s.agreement == 1.0


def test_points_sum_to_the_score():
    reports = [report("financials", conviction=80), report("filings", "bearish", 60), report("price", conviction=40)]
    s = scoring.score_horizon("years", reports)
    assert sum(c.points for c in s.contributions) == pytest.approx(s.score, abs=0.2)


def test_uninformed_neutral_does_not_dilute_but_confident_neutral_does():
    base = [report("financials", conviction=80)]
    uninformed = scoring.score_horizon("years", base + [report("filings", "neutral", 0)])
    confident = scoring.score_horizon("years", base + [report("filings", "neutral", 100)])
    alone = scoring.score_horizon("years", base)
    assert uninformed.score == pytest.approx(alone.score)
    assert confident.score < alone.score


def test_horizon_weights_matter():
    reports = [report("options", conviction=80), report("financials", "bearish", 80)]
    assert scoring.score_horizon("weeks", reports).score > 0  # options dominate short term
    assert scoring.score_horizon("years", reports).score < 0  # financials dominate long term


def test_high_severity_objection_halves_weight_only_on_named_horizons():
    reports = [report("financials", conviction=80), report("filings", "bearish", 80)]
    obj = Objection(
        target="bull",
        claim_challenged="c",
        objection="margins are one-off",
        severity="high",
        affected_analysts=["financials"],
        horizons=["years"],
    )
    before = scoring.score_horizon("years", reports)
    after = scoring.score_horizon("years", reports, challenge([obj]))
    fin = next(c for c in after.contributions if c.analyst_id == "financials")
    assert fin.weight == pytest.approx(0.5)
    assert fin.penalties
    assert after.score < before.score
    months = scoring.score_horizon("months", reports, challenge([obj]))
    assert next(c for c in months.contributions if c.analyst_id == "financials").weight == pytest.approx(0.7)


def test_echo_chamber_group_counts_as_one_analyst():
    reports = [report("price", conviction=80), report("news", conviction=80), report("analysts", conviction=80)]
    group = SharedEvidence(fact="the Q2 earnings beat", analyst_ids=["price", "news", "analysts"])
    s = scoring.score_horizon("weeks", reports, challenge(shared=[group]))
    total = sum(c.weight for c in s.contributions)
    assert total == pytest.approx(1.0, abs=0.005)  # max single weight (price, 1.0); weights are rounded
    assert s.score < scoring.score_horizon("weeks", reports).score


def test_disagreement_lowers_confidence():
    agree = [report(a, conviction=70) for a in ("price", "options", "news")]
    split = [report("price", conviction=70), report("options", "bearish", 70), report("news", conviction=70)]
    assert scoring.score_horizon("weeks", agree).confidence > scoring.score_horizon("weeks", split).confidence


@pytest.mark.parametrize(
    ("score", "rating"),
    [(30, "strong_buy"), (12.6, "buy"), (10, "buy"), (9.9, "hold"), (0, "hold"), (-10, "sell"), (-30, "strong_sell")],
)
def test_rating_bands(score, rating):
    assert scoring.rating_for(score) == rating


def test_assemble_verdict_clamps_judge_and_derives_rating():
    reports = [report(a, conviction=90) for a in scoring.WEIGHTS]
    scores = scoring.score_all(reports)
    ruling = JudgeRuling(
        bottom_line="b",
        reasons_for=["f"],
        reasons_against=["a"],
        summary="s",
        weeks=HorizonRuling(adjustment=-100, adjustment_reason="x", rationale="r"),
        months=HorizonRuling(adjustment=0, adjustment_reason="Formula stands.", rationale="r"),
        years=HorizonRuling(adjustment=0, adjustment_reason="Formula stands.", rationale="r"),
        key_catalysts=[],
        key_risks=[],
        dissenting_analysts=[],
        what_would_change_the_verdict="w",
    )
    v = scoring.assemble_verdict(scores, ruling)
    assert v.weeks.adjustment == -scoring.MAX_JUDGE_ADJUSTMENT
    assert v.weeks.score == pytest.approx(scores["weeks"].score - scoring.MAX_JUDGE_ADJUSTMENT)
    assert v.rating == scoring.rating_for(v.score)
    assert v.rating == "strong_buy"
