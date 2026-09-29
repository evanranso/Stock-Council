"""Analyst price targets, rating mix, and recent upgrades/downgrades."""

from __future__ import annotations

from ..schemas import DataPacket
from . import _yf
from .base import clean, df_records, finnhub, guarded, in_thread, unavailable

SEGMENT = "analysts"


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    targets = await in_thread(_yf.safe_attr, ticker, "analyst_price_targets")
    summary = await in_thread(_yf.safe_attr, ticker, "recommendations_summary")
    changes = await in_thread(_yf.safe_attr, ticker, "upgrades_downgrades")
    info = await in_thread(_yf.info, ticker)

    data: dict = {
        "current_price": info.get("currentPrice"),
        "price_targets": clean(targets) if targets else None,
        "number_of_analysts": info.get("numberOfAnalystOpinions"),
        "consensus_key": info.get("recommendationKey"),
        "consensus_mean_1_strong_buy_to_5_sell": info.get("recommendationMean"),
        "rating_mix_by_month": df_records(summary),
        "recent_rating_changes": df_records(changes, limit=25),
    }
    sources = ["Yahoo Finance (yfinance)"]
    notes: list[str] = []
    try:
        data["finnhub_recommendation_trend"] = (await finnhub("stock/recommendation", symbol=ticker))[:6]
        sources.append("Finnhub")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Finnhub recommendation trend unavailable: {exc}")

    if not data["price_targets"] and not data["rating_mix_by_month"]:
        return unavailable(SEGMENT, ticker, "No analyst coverage found.")
    return DataPacket(segment=SEGMENT, ticker=ticker, sources=sources, notes=notes, data=clean(data))
