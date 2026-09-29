"""Invite codes, credits, refunds, free cached views, cost tracking, and admin endpoints."""

import asyncio
import dataclasses
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import cache, main, usage

ADMIN = {"X-Admin-Key": "secret-admin"}


def events(resp):
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]


@pytest.fixture
def invite_mode(monkeypatch):
    s = dataclasses.replace(main.settings, access_mode="invite", admin_key="secret-admin", max_runs_per_day=0)
    monkeypatch.setattr(main, "settings", s)
    monkeypatch.setattr(main, "_recent_runs", main.defaultdict(main.deque))
    monkeypatch.setattr(main, "_live", {})
    return TestClient(main.app)


def fake_council(outcome: str):
    async def council(symbol):
        usage.record("price", "claude-opus-5-5", SimpleNamespace(input_tokens=10_000, output_tokens=2_000))
        yield {"type": "start", "ticker": symbol, "company_name": "X"}
        if outcome == "done":
            yield {"type": "verdict", "verdict": {"rating": "buy", "score": 30}}
            yield {"type": "done", "run": {"ticker": symbol}}
        else:
            raise RuntimeError("boom")

    return council


def test_invite_required_for_fresh_runs(invite_mode, monkeypatch):
    monkeypatch.setattr(main, "run_council", fake_council("done"))
    refused = events(invite_mode.get("/api/analyze/AAA"))
    assert refused[0]["reason"] == "invite_required"
    assert events(invite_mode.get("/api/analyze/AAA?code=SC-NOPE-NOPE"))[0]["reason"] == "invite_required"


def test_credit_is_charged_and_cached_views_are_free(invite_mode, monkeypatch):
    monkeypatch.setattr(main, "run_council", fake_council("done"))
    monkeypatch.setattr(main.cache, "record_verdict", lambda run: None)
    code = invite_mode.post("/api/admin/invites", json={"label": "Sam", "credits": 1}, headers=ADMIN).json()["code"]

    assert events(invite_mode.get(f"/api/analyze/AAA?code={code.lower()}"))[-1]["type"] == "done"
    assert cache.get_invite(code)["remaining"] == 0

    # Someone else (no code) opening the same ticker gets the cached run for free.
    assert invite_mode.get("/api/status/AAA").json() == {"free": True, "reason": "cached"}
    assert events(invite_mode.get("/api/analyze/AAA"))[0]["cached"] is True

    # Out of credits for a new ticker.
    assert events(invite_mode.get(f"/api/analyze/BBB?code={code}"))[0]["reason"] == "no_credits"


def test_failed_run_refunds_the_credit(invite_mode, monkeypatch):
    monkeypatch.setattr(main, "run_council", fake_council("fail"))
    code = cache.create_invite("Pat", 2)["code"]
    out = events(invite_mode.get(f"/api/analyze/CCC?code={code}"))
    assert out[-1]["type"] == "error"
    assert cache.get_invite(code)["remaining"] == 2


def test_usage_is_recorded_and_reported(invite_mode, monkeypatch):
    monkeypatch.setattr(main, "run_council", fake_council("done"))
    monkeypatch.setattr(main.cache, "record_verdict", lambda run: None)
    code = cache.create_invite("Lee", 3)["code"]
    events(invite_mode.get(f"/api/analyze/DDD?code={code}"))

    assert invite_mode.get("/api/admin/stats").status_code == 401
    stats = invite_mode.get("/api/admin/stats", headers=ADMIN).json()
    run = stats["recent_runs"][0]
    expected = (10_000 * 4 + 2_000 * 20) / 1_000_000
    assert run["ticker"] == "DDD" and run["status"] == "done" and run["invite_label"] == "Lee"
    assert run["cost_usd"] == pytest.approx(expected)
    assert stats["all_time"]["avg_cost_per_completed_run"] == pytest.approx(expected)


def test_admin_can_top_up_and_disable(invite_mode):
    code = invite_mode.post("/api/admin/invites", json={"label": "Kim"}, headers=ADMIN).json()["code"]
    assert cache.get_invite(code)["credits_total"] == main.settings.default_invite_credits
    updated = invite_mode.post(
        f"/api/admin/invites/{code}", json={"add_credits": 5, "disabled": True}, headers=ADMIN
    ).json()
    assert updated["remaining"] == main.settings.default_invite_credits + 5 and updated["disabled"] is True
    assert invite_mode.get(f"/api/access?code={code}").json()["valid"] is False


def test_open_mode_needs_no_code(monkeypatch):
    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, access_mode="open", max_runs_per_day=0))
    monkeypatch.setattr(main, "_recent_runs", main.defaultdict(main.deque))
    monkeypatch.setattr(main, "run_council", fake_council("done"))
    monkeypatch.setattr(main.cache, "record_verdict", lambda run: None)
    assert events(TestClient(main.app).get("/api/analyze/EEE"))[-1]["type"] == "done"


async def test_tracker_collects_calls_from_parallel_tasks():
    tracker = usage.start()

    async def call(agent):
        usage.record(agent, "claude-sonnet-5-5", SimpleNamespace(input_tokens=1_000_000, output_tokens=0))

    await asyncio.gather(*(asyncio.create_task(call(a)) for a in ("a", "b")))
    s = tracker.summary()
    assert s["calls"] == 2 and s["cost_usd"] == pytest.approx(4.0)


def test_price_lookup_handles_unknown_and_suffixed_models():
    assert usage.price_for("claude-opus-4-8-20260101") == (5.0, 25.0)
    assert usage.price_for("something-new") == usage.DEFAULT_PRICE
