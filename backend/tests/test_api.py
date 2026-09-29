import dataclasses
import json

from fastapi.testclient import TestClient

from app import main


def events(resp):
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]


def test_daily_budget_refusal_arrives_as_an_event(monkeypatch):
    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, max_runs_per_day=1))
    monkeypatch.setattr(main.cache, "get_run", lambda t: None)
    monkeypatch.setattr(main, "_daily_runs", {"2000-01-01": 5})  # stale day is dropped
    monkeypatch.setattr(main, "_recent_runs", main.defaultdict(main.deque))

    async def fake_council(symbol):
        yield {"type": "error", "message": "stub run"}

    monkeypatch.setattr(main, "run_council", fake_council)
    client = TestClient(main.app)
    assert events(client.get("/api/analyze/AAA"))[0]["message"] == "stub run"
    refused = events(client.get("/api/analyze/BBB"))
    assert refused[0]["type"] == "error" and "limit" in refused[0]["message"]


def test_rate_limit_uses_proxy_appended_ip(monkeypatch):
    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, trust_proxy=True))
    req = type("R", (), {"headers": {"x-forwarded-for": "6.6.6.6, 203.0.113.9"}, "client": None})()
    assert main._client_ip(req) == "203.0.113.9"
