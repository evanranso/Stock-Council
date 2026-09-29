"""Related markets: sector ETF, peers, broad indices, rates, dollar, volatility, commodities."""

from __future__ import annotations

import pandas as pd

from ..schemas import DataPacket
from . import _yf, sec
from . import indicators as ind
from .base import clean, finnhub, guarded, in_thread, unavailable

SEGMENT = "related"

SECTOR_ETFS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Utilities": "XLU",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}
MACRO = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "IWM": "Russell 2000",
    "^VIX": "VIX",
    "^TNX": "10Y Treasury yield",
    "DX-Y.NYB": "US Dollar index",
    "CL=F": "Crude oil",
    "GC=F": "Gold",
}


def _closes(symbols: list[str]) -> dict[str, pd.Series]:
    out = {}
    for s in symbols:
        try:
            h = _yf.history(s, "1y", "1d")
            if not h.empty:
                out[s] = h["Close"].tz_localize(None) if h.index.tz is not None else h["Close"]
        except Exception:  # noqa: BLE001
            continue
    return out


def _perf(series: pd.Series) -> dict:
    return {
        "1m": ind.pct_change(series, 21),
        "3m": ind.pct_change(series, 63),
        "1y": ind.pct_change(series, len(series) - 1),
    }


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    notes: list[str] = []
    info: dict = {}
    try:
        company = await sec.company_info(ticker)  # SEC works from cloud servers; Yahoo's profile often doesn't
        if company:
            info = {"sector": company["sector"], "industry": company["industry"]}
    except Exception as exc:  # noqa: BLE001
        notes.append(f"SEC company profile unavailable ({type(exc).__name__}).")
    if not info.get("sector"):
        info = await in_thread(_yf.info, ticker) or info
    sector_etf = SECTOR_ETFS.get(info.get("sector") or "")
    peers: list[str] = []
    try:
        peers = [p for p in await finnhub("stock/peers", symbol=ticker) if p != ticker][:6]
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Peer list unavailable (Finnhub): {exc}")

    symbols = [ticker, *MACRO, *([sector_etf] if sector_etf else []), *peers]
    closes = await in_thread(_closes, symbols)
    stock = closes.get(ticker)
    if stock is None:
        return unavailable(SEGMENT, ticker, "No price history for the stock; can't compare it to other markets.")

    def rel(sym: str) -> dict:
        s = closes[sym]
        row = {"symbol": sym, "performance": _perf(s)}
        if sym != ticker:
            row.update(ind.beta_and_corr(stock, s))
        return row

    data = {
        "stock": {
            "symbol": ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "performance": _perf(stock),
        },
        "sector_etf": rel(sector_etf) if sector_etf in closes else None,
        "peers": [rel(p) for p in peers if p in closes],
        "macro_markets": [{**rel(s), "name": MACRO[s]} for s in MACRO if s in closes],
    }
    sources = ["Yahoo Finance (yfinance)"] + (["Finnhub peers"] if peers else [])
    return DataPacket(segment=SEGMENT, ticker=ticker, sources=sources, notes=notes, data=clean(data))
