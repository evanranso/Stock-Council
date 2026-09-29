"""Price charts: trend, momentum, volatility and volume computed from daily bars."""

from __future__ import annotations

from ..schemas import DataPacket
from . import _yf
from . import indicators as ind
from .base import clean, guarded, in_thread, unavailable

SEGMENT = "price"


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    hist = await in_thread(_yf.history, ticker, "2y", "1d")
    if hist is None or hist.empty:
        return unavailable(SEGMENT, ticker, "No price history returned.")

    close, volume = hist["Close"], hist["Volume"]
    last = float(close.iloc[-1])
    year = close.tail(252)
    sma50, sma200 = ind.sma(close, 50), ind.sma(close, 200)

    weekly = close.resample("W").last().tail(52)
    data = {
        "last_close": last,
        "last_date": clean(close.index[-1]),
        "returns": {
            "1w": ind.pct_change(close, 5),
            "1m": ind.pct_change(close, 21),
            "3m": ind.pct_change(close, 63),
            "6m": ind.pct_change(close, 126),
            "1y": ind.pct_change(close, 252),
        },
        "moving_averages": {
            "sma20": ind.sma(close, 20),
            "sma50": sma50,
            "sma200": sma200,
            "price_vs_sma50": last / sma50 - 1 if sma50 else None,
            "price_vs_sma200": last / sma200 - 1 if sma200 else None,
            "golden_cross_active": (sma50 > sma200) if sma50 and sma200 else None,
        },
        "momentum": {"rsi14": ind.rsi(close), "macd": ind.macd(close)},
        "volatility": {
            "annualized_30d": ind.annualized_vol(close, 30),
            "annualized_90d": ind.annualized_vol(close, 90),
            "max_drawdown_1y": ind.max_drawdown(year),
        },
        "range_52w": {
            "high": float(year.max()),
            "low": float(year.min()),
            "pct_from_high": last / float(year.max()) - 1,
            "pct_from_low": last / float(year.min()) - 1,
        },
        "volume": {
            "avg_20d": float(volume.tail(20).mean()),
            "avg_90d": float(volume.tail(90).mean()),
            "last": float(volume.iloc[-1]),
        },
        "weekly_closes_last_52": [{"week": clean(i), "close": round(float(v), 2)} for i, v in weekly.items()],
    }
    return DataPacket(segment=SEGMENT, ticker=ticker, sources=["Yahoo Finance (yfinance)"], data=clean(data))
