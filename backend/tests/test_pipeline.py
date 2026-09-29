"""End-to-end council run with fake data and a fake model: checks isolation and event flow."""

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
    HorizonVerdict,
    HorizonView,
    Outlook,
    Verdict,
)

view = HorizonView(lean="neutral", rationale="r")
OPINION = AnalystOpinion(
    stance="bullish",
    conviction=60,
    headline="h",
    key_findings=[Finding(point="p", evidence="e", implication="bullish")],
    risks_to_view=["x"],
    what_would_change_my_mind="y",
    data_quality="good",
    outlook=Outlook(weeks=view, months=view, years=view),
)
CASE = CaseReport(
    thesis="t",
    arguments=[Argument(claim="c", supporting_analysts=["price"], evidence="e")],
    catalysts=["k"],
    weakest_point="w",
)
CHALLENGE = ChallengeReport(objections=[], leans_that_hold_up=["c"], echo_chamber_check="none", net_assessment="n")
hv = HorizonVerdict(lean="bullish", confidence=55, rationale="r")
VERDICT = Verdict(
    rating="buy",
    confidence=55,
    summary="s",
    weeks=hv,
    months=hv,
    years=hv,
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
            return DataPacket(segment=segment, ticker=ticker, data={"secret": f"{segment}-only-data"})

        return fetch

    async def fake_structured(system, user, schema, effort):
        prompts.setdefault(schema.__name__, []).append(user)
        return {AnalystOpinion: OPINION, CaseReport: CASE, ChallengeReport: CHALLENGE, Verdict: VERDICT}[schema]

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
    run = events[-1]["run"]
    assert run["company_name"] == "Fake Corp"
    congress = next(a for a in run["analysts"] if a["analyst_id"] == "congress")
    assert congress["opinion"] is None and "paid only" in congress["error"]


async def test_specialists_only_see_their_own_packet(fake_world):
    _ = [e async for e in pipeline.run_council("FAKE")]
    specialist_prompts = fake_world["AnalystOpinion"]
    assert len(specialist_prompts) == 11  # congress had no data, so no model call
    for prompt in specialist_prompts:
        leaked = [s.segment for s in specialists.SPECIALISTS if f"{s.segment}-only-data" in prompt]
        assert len(leaked) == 1, f"specialist saw other segments' data: {leaked}"
