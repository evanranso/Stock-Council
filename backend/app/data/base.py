"""Helpers shared by every data adapter."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from functools import lru_cache
from typing import Any

import httpx

from ..config import get_settings
from ..schemas import DataPacket

log = logging.getLogger(__name__)

Fetcher = Callable[[str], Awaitable[DataPacket]]


def clean(value: Any) -> Any:
    """Make pandas/numpy values JSON-safe and compact (NaN -> None, round floats)."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()[:10]
    if hasattr(value, "isoformat"):  # pandas Timestamp
        return value.isoformat()[:10]
    if hasattr(value, "item"):  # numpy scalar
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 4)
    return value


def df_records(df: Any, limit: int | None = None) -> list[dict[str, Any]]:
    """DataFrame -> list of dicts (index included), safe for JSON."""
    if df is None or getattr(df, "empty", True):
        return []
    frame = df.reset_index()
    if limit is not None:
        frame = frame.head(limit)
    return clean(frame.to_dict(orient="records"))


async def in_thread(fn: Callable[..., Any], *args: Any) -> Any:
    """yfinance is synchronous; keep it off the event loop."""
    return await asyncio.to_thread(fn, *args)


@lru_cache
def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=20.0, follow_redirects=True)


async def get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    resp = await _client().get(url, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def get_text(url: str, headers: dict[str, str] | None = None) -> str:
    resp = await _client().get(url, headers=headers)
    resp.raise_for_status()
    return resp.text


def sec_headers() -> dict[str, str]:
    return {"User-Agent": get_settings().sec_user_agent, "Accept-Encoding": "gzip, deflate"}


async def finnhub(path: str, **params: Any) -> Any:
    key = get_settings().finnhub_api_key
    if not key:
        raise RuntimeError("FINNHUB_API_KEY not set")
    return await get_json(f"https://finnhub.io/api/v1/{path}", params={**params, "token": key})


def unavailable(segment: str, ticker: str, reason: str) -> DataPacket:
    return DataPacket(segment=segment, ticker=ticker, status="unavailable", notes=[reason])


def guarded(segment: str) -> Callable[[Fetcher], Fetcher]:
    """Never let one broken source take down the whole council."""

    def wrap(fn: Fetcher) -> Fetcher:
        async def inner(ticker: str) -> DataPacket:
            try:
                return await fn(ticker)
            except Exception as exc:  # noqa: BLE001 - adapters talk to flaky third parties
                log.warning("adapter %s failed for %s: %s", segment, ticker, exc)
                return unavailable(segment, ticker, f"Fetch failed: {type(exc).__name__}: {exc}")

        inner.__name__ = fn.__name__
        return inner

    return wrap
