"""Macro backdrop from FRED: rates, inflation, labor, growth, credit, sentiment.

Uses the FRED API when FRED_API_KEY is set, otherwise FRED's public CSV
download (no key), so this analyst always has data.
"""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import UTC, datetime, timedelta

from ..config import get_settings
from ..schemas import DataPacket
from . import sec
from .base import get_json, get_text, guarded, unavailable

SEGMENT = "economy"
POINTS = 400  # enough history to look a year back, even for daily series

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


def parse_fred_csv(text: str, limit: int = POINTS) -> list[dict]:
    """FRED CSV (date column, value column; '.' = missing) -> newest-first observations."""
    rows = list(csv.reader(io.StringIO(text)))[1:]
    obs = [{"date": r[0], "value": float(r[1])} for r in rows if len(r) >= 2 and r[1] not in (".", "")]
    return list(reversed(obs[-limit:]))


async def _series_api(series_id: str, key: str) -> list[dict]:
    raw = await get_json(
        "https://api.stlouisfed.org/fred/series/observations",
        params={"series_id": series_id, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": POINTS},
    )
    return [{"date": o["date"], "value": float(o["value"])} for o in raw["observations"] if o["value"] != "."]


async def _series_csv(series_id: str) -> list[dict]:
    start = (datetime.now(UTC) - timedelta(days=5 * 365)).date().isoformat()
    text = await get_text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}")
    return parse_fred_csv(text)


def _value_on_or_before(obs: list[dict], day: str) -> float | None:
    """obs is newest first."""
    return next((o["value"] for o in obs if o["date"] <= day), None)


def summarize_series(series_id: str, label: str, obs: list[dict], today: datetime | None = None) -> dict:
    """Latest reading plus where it was 3 and 12 months ago: the trend, without every data point.

    Price indices (CPI) are only meaningful as inflation rates, so they're reported as year-over-year %.
    """
    latest = obs[0]
    anchor = datetime.fromisoformat(latest["date"])
    back = {
        "3m_ago": (anchor - timedelta(days=91)).date().isoformat(),
        "1y_ago": (anchor - timedelta(days=365)).date().isoformat(),
    }
    if series_id in ("CPIAUCSL", "CPILFESL"):
        return {
            "label": ("Core CPI" if series_id == "CPILFESL" else "CPI") + " inflation, year over year (%)",
            "latest": {"date": latest["date"]},
            "yoy_pct": _yoy(obs, latest["date"]),
            "yoy_pct_3m_ago": _yoy(obs, back["3m_ago"]),
        }
    entry: dict = {"label": label, "latest": latest}
    for name, day in back.items():
        v = _value_on_or_before(obs, day)
        if v is not None:
            entry[name] = round(v, 3)
    return entry


def _yoy(obs: list[dict], day: str) -> float | None:
    now = _value_on_or_before(obs, day)
    then = _value_on_or_before(obs, (datetime.fromisoformat(day) - timedelta(days=365)).date().isoformat())
    return round((now / then - 1) * 100, 2) if now and then else None


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    key = get_settings().fred_api_key
    loader = (lambda s: _series_api(s, key)) if key else _series_csv
    results = await asyncio.gather(*(loader(s) for s in SERIES), return_exceptions=True)

    indicators = {}
    for sid, res in zip(SERIES, results, strict=True):
        if isinstance(res, Exception) or not res:
            continue
        indicators[sid] = summarize_series(sid, SERIES[sid], res)
    if not indicators:
        return unavailable(SEGMENT, ticker, "FRED was unreachable.")

    company = None
    try:
        company = await sec.company_info(ticker)
    except Exception:  # noqa: BLE001 - context is optional
        pass
    data = {
        # Just enough company context to judge macro sensitivity; no company data.
        "company_context": {"sector": (company or {}).get("sector"), "industry": (company or {}).get("industry")},
        "indicators": indicators,
    }
    source = "FRED API" if key else "FRED public CSV"
    return DataPacket(segment=SEGMENT, ticker=ticker, sources=[f"{source} (St. Louis Fed)"], data=data)
