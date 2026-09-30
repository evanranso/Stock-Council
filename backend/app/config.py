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
    # "open": anyone can run fresh analyses (still rate-limited). "invite": fresh analyses need an invite
    # code with credits left. Viewing a stock someone already ran recently is always free.
    access_mode: str = os.getenv("ACCESS_MODE", "open").lower()
    default_invite_credits: int = int(os.getenv("DEFAULT_INVITE_CREDITS", "6"))
    # Unlocks /api/admin/* (cost stats, invite codes). Leave unset to disable admin endpoints.
    admin_key: str | None = os.getenv("ADMIN_KEY") or None
    cache_path: str = os.getenv("CACHE_PATH", "stock_council.db")
    cache_ttl_hours: int = int(os.getenv("CACHE_TTL_HOURS", "12"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
