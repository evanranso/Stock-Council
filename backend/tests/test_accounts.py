"""Sign-in verification, free credits, paid starts, refunds, saved history, code redemption, admin by email.

Tokens are real ES256 JWTs signed with a test key, checked by the same code path as production.
Set PG_TEST_URL to also run these against a real Postgres database.
"""

import dataclasses
import json
import os
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth, cache, db, main

SUPABASE = "https://test-project.supabase.co"
KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


def token(sub="user-1", email="a@example.com", key=KEY, **over):
    claims = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "iss": f"{SUPABASE}/auth/v1",
        "role": "authenticated",
        "exp": int(time.time()) + 3600,
        "user_metadata": {"email_verified": True},
        **over,
    }
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test"})


def bearer(**kw):
    return {"Authorization": f"Bearer {token(**kw)}"}


def events(resp):
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]


@pytest.fixture(params=["sqlite"] + (["postgres"] if os.getenv("PG_TEST_URL") else []))
def backend(request, monkeypatch):
    if request.param == "postgres":
        monkeypatch.setenv("DATABASE_URL", os.environ["PG_TEST_URL"])
        db._pool = None
        cache._ready.clear()
        with db.connect() as conn:
            for t in ("runs", "usage", "invites", "verdicts", "accounts", "redemptions", "saved_runs", "payments"):
                conn.execute(f"DROP TABLE IF EXISTS {t}")
    yield request.param
    if request.param == "postgres":
        db._pool = None
        cache._ready.clear()


@pytest.fixture
def client(backend, monkeypatch):
    s = dataclasses.replace(
        main.settings,
        access_mode="accounts",
        supabase_url=SUPABASE,
        free_credits=4,
        free_signups_per_day=50,
        admin_emails=frozenset({"boss@example.com"}),
        admin_key=None,
        max_runs_per_day=0,
    )
    monkeypatch.setattr(main, "settings", s)
    monkeypatch.setattr(auth, "get_settings", lambda: s)
    monkeypatch.setattr(main, "_recent_runs", main.defaultdict(main.deque))
    monkeypatch.setattr(main, "_live", {})
    monkeypatch.setattr(main.cache, "record_verdict", lambda run: None)

    class FakeJwks:
        def get_signing_key_from_jwt(self, _token):
            return type("K", (), {"key": KEY.public_key()})()

    monkeypatch.setattr(auth, "_jwks_client", lambda url: FakeJwks())
    with TestClient(main.app) as c:
        yield c


def council(outcome="done"):
    async def run(symbol, depth=None):
        yield {"type": "start", "ticker": symbol, "company_name": "Acme", "depth": depth}
        if outcome != "done":
            raise RuntimeError("boom")
        yield {"type": "verdict", "verdict": {"rating": "buy", "score": 25, "confidence": 60, "bottom_line": "b"}}
        yield {"type": "done", "run": {"ticker": symbol, "finished_at": "2026-09-30T12:00:00Z", "depth": depth}}

    return run


def wait_idle(symbol):
    for _ in range(200):
        if symbol not in main._live:
            return
        time.sleep(0.01)


# --- token verification ------------------------------------------------------


def test_valid_token_is_accepted(client):
    assert client.get("/api/me", headers=bearer()).json()["email"] == "a@example.com"


@pytest.mark.parametrize(
    "bad",
    [
        {"key": OTHER_KEY},  # forged signature
        {"exp": int(time.time()) - 10},  # expired
        {"aud": "anon"},  # wrong audience
        {"iss": "https://evil.example/auth/v1"},  # wrong issuer
        {"role": "anon"},
    ],
)
def test_bad_tokens_are_rejected(client, bad):
    assert client.get("/api/me", headers=bearer(**bad)).status_code == 401


def test_unverified_email_is_rejected(client):
    assert client.get("/api/me", headers=bearer(user_metadata={"email_verified": False})).status_code == 403


def test_no_token_means_sign_in(client):
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/analyze/AAA/start").status_code == 401


# --- credits -----------------------------------------------------------------


def test_new_account_gets_free_credits_once(client):
    first = client.get("/api/me", headers=bearer()).json()
    assert first["remaining"] == 4 and first["free_granted"] is True
    assert client.get("/api/me", headers=bearer()).json()["remaining"] == 4  # not granted twice


def test_daily_free_cap(client, monkeypatch):
    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, free_signups_per_day=1))
    assert client.get("/api/me", headers=bearer(sub="u1")).json()["remaining"] == 4
    assert client.get("/api/me", headers=bearer(sub="u2")).json()["remaining"] == 0


def test_paid_run_charges_saves_history_and_is_then_free(client, monkeypatch):
    monkeypatch.setattr(main, "run_council", council())
    assert events(client.get("/api/analyze/ACME?depth=standard"))[0]["reason"] == "sign_in"  # GET can't start runs

    started = client.post("/api/analyze/ACME/start?depth=standard", headers=bearer()).json()
    assert started["state"] == "started" and started["remaining"] == 2
    wait_idle("ACME")
    assert client.get("/api/me", headers=bearer()).json()["remaining"] == 2

    # Saved to this account's history, not anyone else's.
    history = client.get("/api/me/history", headers=bearer()).json()
    assert [h["ticker"] for h in history] == ["ACME"] and history[0]["rating"] == "buy"
    full = client.get(f"/api/me/history/{history[0]['id']}", headers=bearer()).json()
    assert full["events"][-1]["type"] == "done"
    assert client.get("/api/me/history", headers=bearer(sub="someone-else")).json() == []
    assert client.get(f"/api/me/history/{history[0]['id']}", headers=bearer(sub="someone-else")).status_code == 404

    # Now cached: anyone can open it for free, and "start" doesn't charge again.
    assert events(client.get("/api/analyze/ACME?depth=quick"))[0]["cached"] is True
    assert client.post("/api/analyze/ACME/start?depth=quick", headers=bearer(sub="u9")).json()["state"] == "cached"


def test_not_enough_credits(client, monkeypatch):
    monkeypatch.setattr(main, "run_council", council())
    client.post("/api/analyze/AAA/start?depth=deep", headers=bearer())  # 3 of 4
    wait_idle("AAA")
    resp = client.post("/api/analyze/BBB/start?depth=standard", headers=bearer())
    assert resp.status_code == 402 and resp.json()["detail"]["reason"] == "no_credits"


def test_failed_run_refunds(client, monkeypatch):
    monkeypatch.setattr(main, "run_council", council("fail"))
    client.post("/api/analyze/FAIL/start?depth=deep", headers=bearer())
    wait_idle("FAIL")
    assert client.get("/api/me", headers=bearer()).json()["remaining"] == 4
    assert client.get("/api/me/history", headers=bearer()).json() == []


def test_redeem_code_once(client):
    client.get("/api/me", headers=bearer())
    code = cache.create_invite("Sam", 6)["code"]
    assert client.post("/api/me/redeem", json={"code": code.lower()}, headers=bearer()).json()["remaining"] == 10
    again = client.post("/api/me/redeem", json={"code": code}, headers=bearer(sub="u2"))
    assert again.status_code == 400


def test_import_and_delete_history(client):
    evts = [
        {"type": "start", "company_name": "Old Co", "depth": "quick"},
        {"type": "verdict", "verdict": {"rating": "hold", "score": 3, "confidence": 40}},
        {"type": "done", "run": {"finished_at": "2026-09-01T00:00:00Z"}},
    ]
    body = {"entries": [{"ticker": "OLD", "events": evts}, {"ticker": "OLD", "events": evts}]}
    assert client.post("/api/me/history/import", json=body, headers=bearer()).json()["imported"] == 2
    rows = client.get("/api/me/history", headers=bearer()).json()
    assert len(rows) == 1  # same run imported twice is stored once
    client.delete(f"/api/me/history/{rows[0]['id']}", headers=bearer())
    assert client.get("/api/me/history", headers=bearer()).json() == []


def test_admin_by_email(client):
    assert client.get("/api/admin/stats", headers=bearer()).status_code == 401
    stats = client.get("/api/admin/stats", headers=bearer(sub="boss", email="Boss@example.com"))
    assert stats.status_code == 200
    client.get("/api/me", headers=bearer(sub="u5", email="u5@example.com"))
    accounts = client.get("/api/admin/accounts", headers=bearer(sub="boss", email="boss@example.com")).json()
    target = next(a for a in accounts if a["email"] == "u5@example.com")
    topped = client.post(
        f"/api/admin/accounts/{target['user_id']}/credits",
        json={"add": 10},
        headers=bearer(sub="boss", email="boss@example.com"),
    ).json()
    assert topped["remaining"] == 14
