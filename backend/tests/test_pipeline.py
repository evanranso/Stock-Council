"""End-to-end council run with fake data and a fake model: checks isolation, event flow, and scoring wiring."""

import pytest

from app.agents import debate, pipeline, specialists
from app.data import _yf
from app.schemas import (
    AnalystOpinion,
    Argument,
    CaseReport,
    ChallengeReport,
    DataPacket,
    Finding,
    HorizonRuling,
    HorizonView,
    JudgeRuling,
    Outlook,
)

bullish = HorizonView(lean="bullish", conviction=60, rationale="r")
OPINION = AnalystOpinion(
    stance="bullish",
    conviction=60,
    headline="h",
    key_findings=[Finding(point="p", evidence="e", implication="bullish")],
    risks_to_view=["x"],
    what_would_change_my_mind="y",
    data_quality="good",
    outlook=Outlook(weeks=bullish, months=bullish, years=bullish),
)
CASE = CaseReport(
    thesis="t",
    arguments=[Argument(claim="c", supporting_analysts=["price"], evidence="e")],
    catalysts=["k"],
    key_points=["kp1", "kp2", "kp3"],
    weakest_point="w",
)
CHALLENGE = ChallengeReport(
    objections=[], leans_that_hold_up=["c"], shared_evidence=[], net_assessment="n", headline="h"
)
# The judge tries to move weeks by 50 points; the formula only allows 15.
RULING = JudgeRuling(
    bottom_line="b",
    reasons_for=["f"],
    reasons_against=["a"],
    summary="s",
    weeks=HorizonRuling(adjustment=50, adjustment_reason="overreach", rationale="r"),
    months=HorizonRuling(adjustment=0, adjustment_reason="Formula stands.", rationale="r"),
    years=HorizonRuling(adjustment=-5, adjustment_reason="minor", rationale="r"),
    key_catalysts=[],
    key_risks=[],
    dissenting_analysts=[],
    what_would_change_the_verdict="w",
)


@pytest.fixture
def fake_world(monkeypatch):
    prompts = {}

    def adapter(segment):
        async def fetch(ticker):
            if segment == "congress":
                return DataPacket(segment=segment, ticker=ticker, status="unavailable", notes=["paid only"])
            data = {"secret": f"{segment}-only-data"}
            if segment == "price":
                data["last_close"] = 123.45
            return DataPacket(segment=segment, ticker=ticker, data=data)

        return fetch

    async def fake_structured(system, user, schema, effort):
        prompts.setdefault(schema.__name__, []).append(user)
        return {AnalystOpinion: OPINION, CaseReport: CASE, ChallengeReport: CHALLENGE, JudgeRuling: RULING}[schema]

    monkeypatch.setattr(pipeline, "ADAPTERS", {s.segment: adapter(s.segment) for s in specialists.SPECIALISTS})
    monkeypatch.setattr(specialists, "structured", fake_structured)
    monkeypatch.setattr(debate, "structured", fake_structured)
    monkeypatch.setattr(_yf, "info", lambda t: {"longName": "Fake Corp"})
    return prompts


async def test_council_runs_all_stages_in_order(fake_world):
    events = [e async for e in pipeline.run_council("FAKE")]
    types = [e["type"] for e in events]
    assert types[0] == "start" and types[-1] == "done"
    assert types.count("analyst") == 12
    assert types.index("verdict") > types.index("challenge") > types.index("case")
    phases = [e["phase"] for e in events if e["type"] == "scores"]
    assert phases == ["baseline", "adjusted"]
    run = events[-1]["run"]
    assert run["company_name"] == "Fake Corp"
    assert run["reference_price"] == 123.45
    congress = next(a for a in run["analysts"] if a["analyst_id"] == "congress")
    assert congress["opinion"] is None and "paid only" in congress["error"]


async def test_verdict_comes_from_the_formula_with_bounded_judge(fake_world):
    events = [e async for e in pipeline.run_council("FAKE")]
    verdict = next(e for e in events if e["type"] == "verdict")["verdict"]
    weeks = verdict["weeks"]
    assert weeks["adjustment"] == 15  # clamped from 50
    assert weeks["score"] == pytest.approx(weeks["formula_score"] + 15)
    assert verdict["years"]["adjustment"] == -5
    # 11 analysts all bullish at 60 -> strongly positive formula, so a Buy-side rating.
    assert verdict["rating"] in ("buy", "strong_buy")
    judge_prompt = fake_world["JudgeRuling"][0]
    assert "<formula_scores>" in judge_prompt


async def test_specialists_only_see_their_own_packet(fake_world):
    _ = [e async for e in pipeline.run_council("FAKE")]
    specialist_prompts = fake_world["AnalystOpinion"]
    assert len(specialist_prompts) == 11  # congress had no data, so no model call
    for prompt in specialist_prompts:
        leaked = [s.segment for s in specialists.SPECIALISTS if f"{s.segment}-only-data" in prompt]
        assert len(leaked) == 1, f"specialist saw other segments' data: {leaked}"
