"""Forward EPS/revenue estimates, estimate revisions, and past beats/misses."""

from __future__ import annotations

from ..schemas import DataPacket
from . import _yf
from .base import clean, df_records, finnhub, guarded, in_thread

SEGMENT = "earnings"


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    fields = [
        "earnings_estimate",
        "revenue_estimate",
        "eps_trend",
        "eps_revisions",
        "earnings_history",
        "growth_estimates",
    ]
    data: dict = {}
    for name in fields:
        data[name] = df_records(await in_thread(_yf.safe_attr, ticker, name))
    calendar = await in_thread(_yf.safe_attr, ticker, "calendar")
    data["next_earnings"] = clean(calendar) if calendar else None

    sources = ["Yahoo Finance (yfinance)"]
    notes: list[str] = []
    try:
        data["finnhub_surprises"] = (await finnhub("stock/earnings", symbol=ticker))[:8]
        sources.append("Finnhub")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Finnhub earnings surprises unavailable: {exc}")

    status = "ok" if data["earnings_estimate"] else "partial"
    return DataPacket(segment=SEGMENT, ticker=ticker, status=status, sources=sources, notes=notes, data=clean(data))
