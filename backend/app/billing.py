"""Payments with Stripe: checkout for plans and credit packs, the billing portal, and webhooks.

Credits are only ever added from a verified Stripe webhook, never from the
browser's word. Each paid invoice (subscriptions, every month) or paid checkout
session (one-time packs) is recorded by its Stripe ID, so a webhook delivered
twice can't add credits twice. Which price gives how many credits is decided
here on the server, from settings, not from anything the client sends.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import stripe

from . import cache
from .config import get_settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Plan:
    id: str  # "plus" | "pro" | "topup"
    name: str
    kind: str  # "subscription" | "payment"
    price_id: str
    credits: int
    blurb: str


class BillingError(Exception):
    def __init__(self, status: int, reason: str, message: str) -> None:
        super().__init__(message)
        self.status, self.reason, self.message = status, reason, message


def plans() -> list[Plan]:
    s = get_settings()
    catalog = [
        ("plus", "Plus", "subscription", s.stripe_price_plus, s.plus_credits, "For checking a few stocks a week."),
        ("pro", "Pro", "subscription", s.stripe_price_pro, s.pro_credits, "For active investors and deep dives."),
        ("topup", "Credit pack", "payment", s.stripe_price_topup, s.topup_credits, "One-time. No subscription."),
    ]
    return [Plan(i, n, k, p, c, b) for i, n, k, p, c, b in catalog if p]


def enabled() -> bool:
    return bool(get_settings().stripe_secret_key and plans())


def _plan(plan_id: str | None) -> Plan | None:
    return next((p for p in plans() if p.id == plan_id), None)


def _plan_for_price(price_id: str | None) -> Plan | None:
    return next((p for p in plans() if p.price_id == price_id), None)


def _client() -> stripe.StripeClient:
    return stripe.StripeClient(get_settings().stripe_secret_key or "")


# --- Prices for display (cached; the Stripe dashboard is the source of truth) -----------

_price_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}


def _price(price_id: str) -> dict[str, Any] | None:
    hit = _price_cache.get(price_id)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    try:
        p = _client().v1.prices.retrieve(price_id)
        info = {
            "amount": (p.unit_amount or 0) / 100,
            "currency": p.currency,
            "interval": p.recurring.interval if p.recurring else None,
        }
    except Exception as exc:  # noqa: BLE001 - show the plan without a price rather than failing the page
        log.warning("Billing: couldn't load price %s (%s)", price_id, type(exc).__name__)
        info = None
    _price_cache[price_id] = (time.time(), info)
    return info


def public_plans() -> dict[str, Any]:
    if not enabled():
        return {"enabled": False, "plans": []}
    return {
        "enabled": True,
        "plans": [
            {
                "id": p.id,
                "name": p.name,
                "kind": p.kind,
                "credits": p.credits,
                "blurb": p.blurb,
                "price": _price(p.price_id),
            }
            for p in plans()
        ],
    }


# --- Checkout and portal ---------------------------------------------------------------


def _existing_customer(user_id: str) -> str | None:
    """The account's Stripe customer, if Stripe still knows it.

    Customers made with test keys don't exist in live mode (and vice versa), and a customer can be
    deleted in the dashboard. Then the stored ID and its plan are stale: forget them and start fresh.
    """
    existing = cache.stripe_customer(user_id)
    if not existing:
        return None
    try:
        customer = _client().v1.customers.retrieve(existing)
        if not getattr(customer, "deleted", False):
            return existing
    except stripe.InvalidRequestError as exc:
        if getattr(exc, "code", None) != "resource_missing":
            raise
    log.info("Billing: stored customer %s no longer exists; starting fresh for %s", existing, user_id)
    cache.clear_billing(user_id)
    return None


def _customer_for(user_id: str, email: str | None) -> str:
    existing = _existing_customer(user_id)
    if existing:
        return existing
    params: dict[str, Any] = {"metadata": {"user_id": user_id}}
    if email:
        params["email"] = email
    customer = _client().v1.customers.create(params=params)
    cache.set_stripe_customer(user_id, customer.id)
    return customer.id


def checkout(user_id: str, email: str | None, plan_id: str) -> str:
    """Create a Stripe Checkout page for this plan and return its URL."""
    plan = _plan(plan_id)
    if not enabled() or not plan:
        raise BillingError(400, "unknown_plan", "That plan isn't available.")
    customer = _customer_for(user_id, email)  # first: clears a stale plan if the customer is gone
    account = cache.get_account(user_id) or {}
    if (
        plan.kind == "subscription"
        and account.get("plan")
        and account.get("plan_status") in ("active", "trialing", "past_due")
    ):
        # One subscription per account: changing plans happens in Stripe's billing portal.
        raise BillingError(409, "has_subscription", "You already have a plan. Change it from Manage billing.")
    site = get_settings().site_url
    meta = {"user_id": user_id, "plan": plan.id}
    params: dict[str, Any] = {
        "mode": plan.kind,
        "customer": customer,
        "line_items": [{"price": plan.price_id, "quantity": 1}],
        "client_reference_id": user_id,
        "metadata": meta,
        "allow_promotion_codes": True,
        "success_url": f"{site}/pricing?success=1",
        "cancel_url": f"{site}/pricing?canceled=1",
    }
    if plan.kind == "subscription":
        params["subscription_data"] = {"metadata": meta}
    else:
        params["payment_intent_data"] = {"metadata": meta}
    session = _client().v1.checkout.sessions.create(params=params)
    return session.url


def portal(user_id: str) -> str:
    """Stripe's billing portal: change or cancel a plan, update the card, download invoices."""
    customer = _existing_customer(user_id)
    if not customer:
        raise BillingError(400, "no_billing", "No billing account yet. Buy a plan or credits first.")
    session = _client().v1.billing_portal.sessions.create(
        params={"customer": customer, "return_url": f"{get_settings().site_url}/pricing"}
    )
    return session.url


# --- Webhooks --------------------------------------------------------------------------


def parse_webhook(payload: bytes, signature: str | None) -> dict[str, Any]:
    """Verify Stripe's signature, then return the event as plain JSON."""
    secret = get_settings().stripe_webhook_secret
    if not secret:
        raise BillingError(404, "disabled", "Webhooks aren't configured.")
    try:
        stripe.Webhook.construct_event(payload, signature or "", secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise BillingError(400, "bad_signature", "Invalid signature.") from exc
    return json.loads(payload)


def _id(value: Any) -> str | None:
    """Stripe fields can be an ID string or an expanded object."""
    if isinstance(value, dict):
        return value.get("id")
    return value


def _invoice_subscription(inv: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """(subscription id, subscription metadata) across old and new Stripe API versions."""
    details = ((inv.get("parent") or {}).get("subscription_details")) or {}
    sub = _id(inv.get("subscription")) or _id(details.get("subscription"))
    meta = details.get("metadata") or inv.get("subscription_details", {}).get("metadata") or {}
    return sub, meta


def _invoice_prices(inv: dict[str, Any]) -> list[str]:
    prices = []
    for line in (inv.get("lines") or {}).get("data", []):
        price = _id(line.get("price")) or _id(((line.get("pricing") or {}).get("price_details") or {}).get("price"))
        if price:
            prices.append(price)
    return prices


def _sub_period_end(sub: dict[str, Any]) -> float | None:
    end = sub.get("current_period_end")
    if not end:
        items = (sub.get("items") or {}).get("data") or []
        end = items[0].get("current_period_end") if items else None
    return float(end) if end else None


def handle_event(event: dict[str, Any]) -> str:
    """Apply one verified Stripe event. Returns a short outcome for logs and tests."""
    kind = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        meta = obj.get("metadata") or {}
        user_id = meta.get("user_id") or obj.get("client_reference_id")
        if obj.get("customer") and user_id and not cache.stripe_customer(user_id):
            cache.set_stripe_customer(user_id, _id(obj["customer"]))
        if obj.get("mode") != "payment":
            return "subscription checkout: credits come with the paid invoice"
        if obj.get("payment_status") != "paid":
            return "not paid yet"
        plan = _plan(meta.get("plan"))
        if not plan or plan.kind != "payment" or not user_id:
            return "ignored: unknown plan or user"
        added = cache.grant_payment(
            obj["id"],
            user_id,
            "payment",
            plan.id,
            plan.credits,
            obj.get("amount_total") or 0,
            obj.get("currency") or "",
        )
        return f"granted {plan.credits}" if added else "duplicate"

    if kind == "invoice.paid":
        if obj.get("billing_reason") not in ("subscription_create", "subscription_cycle"):
            return "ignored: not a new period"  # e.g. proration when switching plans mid-month
        sub_id, meta = _invoice_subscription(obj)
        user_id = cache.user_for_customer(_id(obj.get("customer")) or "") or meta.get("user_id")
        plan = next((p for p in map(_plan_for_price, _invoice_prices(obj)) if p), None) or _plan(meta.get("plan"))
        if not user_id or not plan or plan.kind != "subscription":
            log.warning("Billing: invoice %s has no matching account or plan", obj.get("id"))
            return "ignored: unknown plan or user"
        added = cache.grant_payment(
            obj["id"],
            user_id,
            "subscription",
            plan.id,
            plan.credits,
            obj.get("amount_paid") or 0,
            obj.get("currency") or "",
        )
        return f"granted {plan.credits}" if added else "duplicate"

    if kind in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        user_id = cache.user_for_customer(_id(obj.get("customer")) or "") or (obj.get("metadata") or {}).get("user_id")
        if not user_id:
            return "ignored: unknown customer"
        items = (obj.get("items") or {}).get("data") or []
        plan = _plan_for_price(_id(items[0].get("price")) if items else None) or _plan(
            (obj.get("metadata") or {}).get("plan")
        )
        if kind.endswith("deleted") or obj.get("status") in ("canceled", "incomplete_expired"):
            cache.set_subscription(user_id, None, "canceled", None, None)
            return "subscription ended"
        status = "canceling" if obj.get("cancel_at_period_end") else obj.get("status")
        cache.set_subscription(user_id, plan.id if plan else None, status, obj.get("id"), _sub_period_end(obj))
        return f"subscription {status}"

    return "ignored"
