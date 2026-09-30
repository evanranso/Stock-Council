"""Runtime settings, read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass


def _list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
    specialist_effort: str = os.getenv("SPECIALIST_EFFORT", "medium")
    debate_effort: str = os.getenv("DEBATE_EFFORT", "high")
    max_parallel_agents: int = int(os.getenv("MAX_PARALLEL_AGENTS", "6"))

    finnhub_api_key: str | None = os.getenv("FINNHUB_API_KEY") or None
    fred_api_key: str | None = os.getenv("FRED_API_KEY") or None
    # SEC requires a descriptive User-Agent with contact info on every request.
    sec_user_agent: str = os.getenv("SEC_USER_AGENT", "StockCouncil contact@example.com")

    allowed_origins: list[str] = field(
        default_factory=lambda: _list(os.getenv("ALLOWED_ORIGINS", "http://localhost:3000"))
    )
    # e.g. https://.*\.stock-council\.pages\.dev for Cloudflare preview deploys
    allowed_origin_regex: str | None = os.getenv("ALLOWED_ORIGIN_REGEX") or None
    rate_limit_per_hour: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "10"))
    # Hard ceiling on new (uncached) council runs per UTC day, across all visitors. 0 = no limit.
    max_runs_per_day: int = int(os.getenv("MAX_RUNS_PER_DAY", "40"))
    # Behind a hosting proxy (Render, Railway, Fly) the real visitor IP is in X-Forwarded-For.
    trust_proxy: bool = os.getenv("TRUST_PROXY", "false").lower() == "true"
    # Supabase: sign-in tokens are verified against this project's public keys.
    supabase_url: str | None = (os.getenv("SUPABASE_URL") or "").rstrip("/") or None
    supabase_jwt_secret: str | None = os.getenv("SUPABASE_JWT_SECRET") or None  # only for legacy HS256 projects
    # Who may run fresh (paid) analyses. Viewing a stock someone already ran recently is always free.
    #   "accounts": signed-in, email-verified users spend their credits (default when SUPABASE_URL is set)
    #   "invite":   legacy invite codes as credit wallets, no sign-in
    #   "open":     anyone, rate-limited (local development)
    access_mode: str = (os.getenv("ACCESS_MODE") or ("accounts" if os.getenv("SUPABASE_URL") else "open")).lower()
    # Credits every new verified account gets once. 4 = two Standard analyses.
    free_credits: int = int(os.getenv("FREE_CREDITS", "4"))
    # Safety valve: at most this many accounts get free credits per 24h (0 = no cap).
    free_signups_per_day: int = int(os.getenv("FREE_SIGNUPS_PER_DAY", "50"))
    admin_emails: frozenset[str] = frozenset(e.lower() for e in _list(os.getenv("ADMIN_EMAILS", "")))
    default_invite_credits: int = int(os.getenv("DEFAULT_INVITE_CREDITS", "6"))
    # Unlocks /api/admin/* (cost stats, invite codes). Leave unset to disable admin endpoints.
    admin_key: str | None = os.getenv("ADMIN_KEY") or None
    # Payments (Stripe). Billing is off until STRIPE_SECRET_KEY and at least one price are set.
    stripe_secret_key: str | None = os.getenv("STRIPE_SECRET_KEY") or None
    stripe_webhook_secret: str | None = os.getenv("STRIPE_WEBHOOK_SECRET") or None
    # Price IDs from the Stripe dashboard (price_...). Plus and Pro are monthly subscriptions; Top-up is one-time.
    stripe_price_plus: str | None = os.getenv("STRIPE_PRICE_PLUS") or None
    stripe_price_pro: str | None = os.getenv("STRIPE_PRICE_PRO") or None
    stripe_price_topup: str | None = os.getenv("STRIPE_PRICE_TOPUP") or None
    # Credits each purchase adds (subscriptions: every month, on each paid invoice).
    plus_credits: int = int(os.getenv("PLUS_CREDITS", "20"))
    pro_credits: int = int(os.getenv("PRO_CREDITS", "60"))
    topup_credits: int = int(os.getenv("TOPUP_CREDITS", "10"))
    # Public site address, for Stripe's return links. Defaults to the first ALLOWED_ORIGINS entry.
    site_url: str = (os.getenv("SITE_URL") or _list(os.getenv("ALLOWED_ORIGINS", "http://localhost:3000"))[0]).rstrip(
        "/"
    )
    cache_path: str = os.getenv("CACHE_PATH", "stock_council.db")
    cache_ttl_hours: int = int(os.getenv("CACHE_TTL_HOURS", "12"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
