"""Macro backdrop from FRED: rates, inflation, labor, growth, credit, sentiment."""

from __future__ import annotations

import asyncio

from ..config import get_settings
from ..schemas import DataPacket
from . import _yf
from .base import get_json, guarded, in_thread, unavailable

SEGMENT = "economy"

SERIES = {
    "FEDFUNDS": "Effective fed funds rate (%)",
    "DGS2": "2Y Treasury yield (%)",
    "DGS10": "10Y Treasury yield (%)",
    "T10Y2Y": "10Y minus 2Y spread (pp)",
    "CPIAUCSL": "CPI index (all items)",
    "CPILFESL": "Core CPI index",
    "UNRATE": "Unemployment rate (%)",
    "PAYEMS": "Nonfarm payrolls (thousands)",
    "ICSA": "Initial jobless claims",
    "A191RL1Q225SBEA": "Real GDP growth, annualized q/q (%)",
    "BAMLH0A0HYM2": "High-yield credit spread (%)",
    "UMCSENT": "UMich consumer sentiment",
}


async def _series(series_id: str, key: str) -> list[dict]:
    raw = await get_json(
        "https://api.stlouisfed.org/fred/series/observations",
        params={"series_id": series_id, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 14},
    )
    return [{"date": o["date"], "value": float(o["value"])} for o in raw["observations"] if o["value"] != "."]


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    key = get_settings().fred_api_key
    if not key:
        return unavailable(SEGMENT, ticker, "FRED_API_KEY not set (free at fred.stlouisfed.org).")

    results = await asyncio.gather(*(_series(s, key) for s in SERIES), return_exceptions=True)
    indicators = {}
    for sid, res in zip(SERIES, results, strict=True):
        if isinstance(res, Exception) or not res:
            continue
        entry = {"label": SERIES[sid], "latest": res[0], "history_newest_first": res}
        if sid in ("CPIAUCSL", "CPILFESL") and len(res) >= 13:
            entry["yoy_pct"] = round((res[0]["value"] / res[12]["value"] - 1) * 100, 2)
        indicators[sid] = entry

    info = await in_thread(_yf.info, ticker)
    data = {
        # Just enough company context to judge macro sensitivity; no company data.
        "company_context": {"sector": info.get("sector"), "industry": info.get("industry"), "beta": info.get("beta")},
        "indicators": indicators,
    }
    return DataPacket(segment=SEGMENT, ticker=ticker, sources=["FRED (St. Louis Fed)"], data=data)
