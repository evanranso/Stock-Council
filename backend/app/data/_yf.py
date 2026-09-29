"""Thin cached access to yfinance so adapters don't refetch the same ticker."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yfinance as yf


@lru_cache(maxsize=256)
def ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol)


def info(symbol: str) -> dict[str, Any]:
    try:
        return ticker(symbol).info or {}
    except Exception:  # noqa: BLE001 - yfinance raises many things on bad symbols
        return {}


def history(symbol: str, period: str = "2y", interval: str = "1d") -> Any:
    return ticker(symbol).history(period=period, interval=interval, auto_adjust=True)


def safe_attr(symbol: str, name: str) -> Any:
    """Read a yfinance property, returning None instead of raising."""
    try:
        return getattr(ticker(symbol), name)
    except Exception:  # noqa: BLE001
        return None
