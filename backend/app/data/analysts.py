"""Sell-side view: rating mix over time (Finnhub, free key) plus price targets and upgrades when Yahoo allows."""

from __future__ import annotations

from ..schemas import DataPacket
from . import _yf
from .base import clean, df_records, finnhub, guarded, in_thread, unavailable

SEGMENT = "analysts"


def _yahoo(ticker: str) -> dict:
    info = _yf.info(ticker)
    targets = _yf.safe_attr(ticker, "analyst_price_targets")
    return {
        "price_targets": clean(targets) if targets else None,
        "number_of_analysts": info.get("numberOfAnalystOpinions"),
        "consensus_key": info.get("recommendationKey"),
        "rating_mix_by_month": df_records(_yf.safe_attr(ticker, "recommendations_summary")),
        "recent_rating_changes": df_records(_yf.safe_attr(ticker, "upgrades_downgrades"), limit=12),
    }


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    data: dict = {}
    sources: list[str] = []
    notes: list[str] = []
    try:
        trend = await finnhub("stock/recommendation", symbol=ticker)
        if trend:
            data["recommendation_trend_by_month"] = trend[:6]
            sources.append("Finnhub recommendation trends")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Finnhub unavailable ({exc}).")

    yahoo = await in_thread(_yahoo, ticker)
    if yahoo["price_targets"] or yahoo["rating_mix_by_month"]:
        data.update({k: v for k, v in yahoo.items() if v})
        sources.append("Yahoo Finance")
    else:
        notes.append(
            "Price targets unavailable (Yahoo blocks most cloud servers; a paid source such as FMP adds them)."
        )

    if not data:
        return unavailable(
            SEGMENT, ticker, "No analyst data. Add a free FINNHUB_API_KEY in Render to enable rating trends."
        )
    return DataPacket(
        segment=SEGMENT,
        ticker=ticker,
        status="ok" if "price_targets" in data else "partial",
        sources=sources,
        notes=notes,
        data=clean(data),
    )
