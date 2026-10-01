"""Stripe billing: signed webhooks only, credits exactly once, subscriptions, checkout parameters."""

import dataclasses
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from test_accounts import backend, bearer  # noqa: F401 - fixture reuse
from test_accounts import client as accounts_client  # noqa: F401 - fixture reuse

from app import billing, cache, main

WHSEC = "whsec_test_secret"


@pytest.fixture
def stripe_on(monkeypatch):
    s = dataclasses.replace(
        main.settings,
        stripe_secret_key="sk_test_x",
        stripe_webhook_secret=WHSEC,
        stripe_price_plus="price_plus",
        stripe_price_pro="price_pro",
        stripe_price_topup="price_topup",
        plus_credits=20,
        pro_credits=60,
        topup_credits=10,
        site_url="https://site.example",
    )
    monkeypatch.setattr(billing, "get_settings", lambda: s)
    monkeypatch.setattr(billing, "_price", lambda pid: {"amount": 9.99, "currency": "usd", "interval": "month"})
    return s


def signed(event: dict, secret: str = WHSEC) -> tuple[bytes, dict]:
    payload = json.dumps(event).encode()
    t = int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return payload, {"stripe-signature": f"t={t},v1={sig}", "content-type": "application/json"}


def post_event(client, event, secret=WHSEC):
    payload, headers = signed(event, secret)
    return client.post("/api/stripe/webhook", content=payload, headers=headers)


def me(client, **kw):
    return client.get("/api/me", headers=bearer(**kw)).json()


@pytest.fixture
def client(accounts_client, stripe_on):  # noqa: F811
    me(accounts_client)  # create user-1 with 4 free credits
    cache.set_stripe_customer("user-1", "cus_1")
    return accounts_client


def topup_session(sid="cs_1", paid="paid"):
    return {
        "id": "evt_" + sid,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": sid,
                "mode": "payment",
                "payment_status": paid,
                "customer": "cus_1",
                "client_reference_id": "user-1",
                "metadata": {"user_id": "user-1", "plan": "topup"},
                "amount_total": 500,
                "currency": "usd",
            }
        },
    }


def invoice(iid="in_1", reason="subscription_cycle", price="price_plus", new_api=True):
    line = {"pricing": {"price_details": {"price": price}}} if new_api else {"price": {"id": price}}
    inv = {
        "id": iid,
        "customer": "cus_1",
        "billing_reason": reason,
        "amount_paid": 999,
        "currency": "usd",
        "lines": {"data": [line]},
    }
    if new_api:
        inv["parent"] = {"subscription_details": {"subscription": "sub_1", "metadata": {"user_id": "user-1"}}}
    else:
        inv["subscription"] = "sub_1"
    return {"id": "evt_" + iid, "type": "invoice.paid", "data": {"object": inv}}


def test_unsigned_or_forged_webhooks_are_rejected(client):
    assert client.post("/api/stripe/webhook", content=b"{}").status_code == 400
    assert post_event(client, topup_session(), secret="whsec_wrong").status_code == 400
    assert me(client)["remaining"] == 4


def test_topup_adds_credits_exactly_once(client):
    assert post_event(client, topup_session()).json()["outcome"] == "granted 10"
    assert post_event(client, topup_session()).json()["outcome"] == "duplicate"  # Stripe retries
    assert me(client)["remaining"] == 14


def test_unpaid_checkout_adds_nothing_until_paid(client):
    assert post_event(client, topup_session("cs_2", paid="unpaid")).json()["outcome"] == "not paid yet"
    late = topup_session("cs_2")
    late["type"] = "checkout.session.async_payment_succeeded"
    assert post_event(client, late).json()["outcome"] == "granted 10"
    assert me(client)["remaining"] == 14


def test_credits_come_from_server_plan_not_client_metadata(client):
    evt = topup_session("cs_3")
    evt["data"]["object"]["metadata"]["plan"] = "plus"  # a subscription plan can't be bought as a one-time payment
    assert post_event(client, evt).json()["outcome"].startswith("ignored")
    assert me(client)["remaining"] == 4


@pytest.mark.parametrize("new_api", [True, False])
def test_subscription_credits_each_month_and_not_on_plan_changes(client, new_api):
    assert post_event(client, invoice("in_a", "subscription_create", new_api=new_api)).json()["outcome"] == "granted 20"
    assert post_event(client, invoice("in_b", "subscription_cycle", new_api=new_api)).json()["outcome"] == "granted 20"
    assert post_event(client, invoice("in_b", "subscription_cycle", new_api=new_api)).json()["outcome"] == "duplicate"
    assert (
        post_event(client, invoice("in_c", "subscription_update", new_api=new_api))
        .json()["outcome"]
        .startswith("ignored")
    )
    assert me(client)["remaining"] == 44


def test_subscription_status_and_cancel(client):
    sub = {
        "id": "sub_1",
        "customer": "cus_1",
        "status": "active",
        "cancel_at_period_end": False,
        "items": {"data": [{"price": {"id": "price_pro"}, "current_period_end": 1_900_000_000}]},
    }
    post_event(client, {"type": "customer.subscription.created", "data": {"object": sub}})
    m = me(client)
    assert (m["plan"], m["plan_status"], m["plan_renews"]) == ("pro", "active", 1_900_000_000)
    post_event(
        client, {"type": "customer.subscription.updated", "data": {"object": {**sub, "cancel_at_period_end": True}}}
    )
    assert me(client)["plan_status"] == "canceling"
    post_event(client, {"type": "customer.subscription.deleted", "data": {"object": {**sub, "status": "canceled"}}})
    m = me(client)
    assert (m["plan"], m["plan_status"]) == (None, "canceled")


class FakeStripe:
    def __init__(self):
        self.calls = []
        v1 = SimpleNamespace(
            customers=SimpleNamespace(create=self._customer),
            checkout=SimpleNamespace(sessions=SimpleNamespace(create=self._checkout)),
            billing_portal=SimpleNamespace(sessions=SimpleNamespace(create=self._portal)),
        )
        self.v1 = v1

    def _customer(self, params):
        self.calls.append(("customer", params))
        return SimpleNamespace(id="cus_new")

    def _checkout(self, params):
        self.calls.append(("checkout", params))
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_x")

    def _portal(self, params):
        self.calls.append(("portal", params))
        return SimpleNamespace(url="https://billing.stripe.com/p/session/x")


def test_checkout_creates_customer_and_session(client, monkeypatch):
    fake = FakeStripe()
    monkeypatch.setattr(billing, "_client", lambda: fake)
    resp = client.post("/api/billing/checkout", json={"plan": "plus"}, headers=bearer(sub="u2", email="u2@example.com"))
    assert resp.json()["url"].startswith("https://checkout.stripe.com/")
    (_, cust), (_, params) = fake.calls
    assert cust["email"] == "u2@example.com" and cust["metadata"]["user_id"] == "u2"
    assert params["mode"] == "subscription" and params["customer"] == "cus_new"
    assert params["line_items"] == [{"price": "price_plus", "quantity": 1}]
    assert params["subscription_data"]["metadata"] == {"user_id": "u2", "plan": "plus"}
    assert params["success_url"] == "https://site.example/pricing?success=1"
    # The customer is remembered: no second customer next time.
    client.post("/api/billing/checkout", json={"plan": "topup"}, headers=bearer(sub="u2", email="u2@example.com"))
    assert [c for c, _ in fake.calls].count("customer") == 1
    assert fake.calls[-1][1]["mode"] == "payment"


def test_second_subscription_is_refused_and_unknown_plan_rejected(client, monkeypatch):
    monkeypatch.setattr(billing, "_client", lambda: FakeStripe())
    cache.set_subscription("user-1", "plus", "active", "sub_1", None)
    resp = client.post("/api/billing/checkout", json={"plan": "pro"}, headers=bearer())
    assert resp.status_code == 409 and resp.json()["detail"]["reason"] == "has_subscription"
    assert client.post("/api/billing/checkout", json={"plan": "free-lol"}, headers=bearer()).status_code == 400
    assert client.post("/api/billing/checkout", json={"plan": "topup"}).status_code == 401  # signed in only
    assert client.post("/api/billing/portal", headers=bearer()).json()["url"].startswith("https://billing.stripe.com")


def test_plans_and_admin_revenue(client):
    plans = client.get("/api/billing/plans").json()
    assert plans["enabled"] and [p["id"] for p in plans["plans"]] == ["plus", "pro", "topup"]
    post_event(client, topup_session("cs_9"))
    stats = client.get("/api/admin/stats", headers=bearer(sub="boss", email="boss@example.com")).json()
    assert stats["today"]["revenue"] == 5.0 and stats["today"]["credits_sold"] == 10
    assert stats["recent_payments"][0]["email"] == "a@example.com"


def test_billing_off_without_keys(accounts_client):  # noqa: F811
    assert accounts_client.get("/api/billing/plans").json() == {"enabled": False, "plans": []}


def test_stripe_errors_come_back_readable(client, monkeypatch):
    import stripe

    class Broken(FakeStripe):
        def _checkout(self, params):
            raise stripe.InvalidRequestError("No such price: 'price_plus'", param="line_items")

    monkeypatch.setattr(billing, "_client", lambda: Broken())
    resp = client.post("/api/billing/checkout", json={"plan": "plus"}, headers=bearer())
    assert resp.status_code == 502
    assert resp.json()["detail"] == {"reason": "stripe_error", "message": "Stripe: No such price: 'price_plus'"}

    def crash(*a):
        raise RuntimeError("boom")

    monkeypatch.setattr(billing, "checkout", crash)
    resp = client.post("/api/billing/checkout", json={"plan": "plus"}, headers=bearer())
    assert resp.status_code == 500 and resp.json()["detail"]["reason"] == "billing_error"


def test_checkout_rate_limit_is_a_clean_429(client, monkeypatch):
    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, rate_limit_per_hour=1))
    monkeypatch.setattr(billing, "_client", lambda: FakeStripe())
    assert client.post("/api/billing/checkout", json={"plan": "topup"}, headers=bearer()).status_code == 200
    resp = client.post("/api/billing/checkout", json={"plan": "topup"}, headers=bearer())
    assert resp.status_code == 429 and resp.json()["detail"]["reason"] == "rate_limit"
