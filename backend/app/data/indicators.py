"""Pure math for technical and options metrics. No I/O, so it is easy to test."""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise
from typing import Any

import pandas as pd


def sma(series: pd.Series, window: int) -> float | None:
    if len(series) < window:
        return None
    return float(series.tail(window).mean())


def rsi(series: pd.Series, window: int = 14) -> float | None:
    if len(series) <= window:
        return None
    delta = series.diff().dropna()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False).mean()
    last_loss = float(loss.iloc[-1])
    if last_loss == 0:
        return 100.0
    rs = float(gain.iloc[-1]) / last_loss
    return 100 - 100 / (1 + rs)


def macd(series: pd.Series) -> dict[str, float] | None:
    if len(series) < 35:
        return None
    fast = series.ewm(span=12, adjust=False).mean()
    slow = series.ewm(span=26, adjust=False).mean()
    line = fast - slow
    signal = line.ewm(span=9, adjust=False).mean()
    return {
        "macd": float(line.iloc[-1]),
        "signal": float(signal.iloc[-1]),
        "histogram": float((line - signal).iloc[-1]),
    }


def pct_change(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods:
        return None
    return float(series.iloc[-1] / series.iloc[-1 - periods] - 1)


def annualized_vol(series: pd.Series, window: int = 30) -> float | None:
    rets = series.pct_change().dropna().tail(window)
    if len(rets) < window // 2:
        return None
    return float(rets.std() * math.sqrt(252))


def max_drawdown(series: pd.Series) -> float | None:
    if series.empty:
        return None
    running_max = series.cummax()
    return float((series / running_max - 1).min())


def beta_and_corr(stock: pd.Series, bench: pd.Series) -> dict[str, float | None]:
    joined = pd.concat([stock.pct_change(), bench.pct_change()], axis=1, join="inner").dropna()
    if len(joined) < 30:
        return {"beta": None, "correlation": None}
    s, b = joined.iloc[:, 0], joined.iloc[:, 1]
    var = float(b.var())
    return {
        "beta": float(s.cov(b) / var) if var else None,
        "correlation": float(s.corr(b)),
    }


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------


def max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
    """Strike at which total option-holder payout at expiry is smallest."""
    strikes = sorted(set(calls["strike"]).union(puts["strike"]))
    if not strikes:
        return None
    c_oi = calls.set_index("strike")["openInterest"].fillna(0)
    p_oi = puts.set_index("strike")["openInterest"].fillna(0)
    best, best_pain = None, float("inf")
    for s in strikes:
        pain = sum(max(0.0, s - k) * oi for k, oi in c_oi.items()) + sum(max(0.0, k - s) * oi for k, oi in p_oi.items())
        if pain < best_pain:
            best, best_pain = s, pain
    return float(best) if best is not None else None


def nearest_row(df: pd.DataFrame, strike: float) -> pd.Series | None:
    if df.empty:
        return None
    return df.iloc[(df["strike"] - strike).abs().argsort().iloc[0]]


def chain_summary(calls: pd.DataFrame, puts: pd.DataFrame, spot: float) -> dict[str, Any]:
    call_vol = float(calls["volume"].fillna(0).sum())
    put_vol = float(puts["volume"].fillna(0).sum())
    call_oi = float(calls["openInterest"].fillna(0).sum())
    put_oi = float(puts["openInterest"].fillna(0).sum())

    atm_call = nearest_row(calls, spot)
    atm_put = nearest_row(puts, spot)
    otm_put = nearest_row(puts, spot * 0.9)
    otm_call = nearest_row(calls, spot * 1.1)

    straddle = None
    if atm_call is not None and atm_put is not None:
        straddle = float((atm_call["lastPrice"] or 0) + (atm_put["lastPrice"] or 0))

    def iv(row: pd.Series | None) -> float | None:
        return float(row["impliedVolatility"]) if row is not None and pd.notna(row["impliedVolatility"]) else None

    put_iv, call_iv = iv(otm_put), iv(otm_call)
    return {
        "put_call_volume_ratio": put_vol / call_vol if call_vol else None,
        "put_call_oi_ratio": put_oi / call_oi if call_oi else None,
        "total_call_volume": call_vol,
        "total_put_volume": put_vol,
        "atm_iv": iv(atm_call),
        "skew_10pct_otm_put_minus_call_iv": (put_iv - call_iv) if put_iv is not None and call_iv is not None else None,
        "implied_move_pct": straddle / spot if straddle and spot else None,
        "max_pain": max_pain(calls, puts),
    }


def unusual_activity(df: pd.DataFrame, kind: str, top: int = 5) -> list[dict[str, Any]]:
    """Contracts trading more today than their entire open interest."""
    frame = df.copy()
    frame["volume"] = frame["volume"].fillna(0)
    frame["openInterest"] = frame["openInterest"].fillna(0)
    hot = frame[(frame["volume"] > 500) & (frame["volume"] > frame["openInterest"])]
    hot = hot.sort_values("volume", ascending=False).head(top)
    return [
        {
            "type": kind,
            "strike": float(r.strike),
            "volume": int(r.volume),
            "open_interest": int(r.openInterest),
            "iv": float(r.impliedVolatility) if pd.notna(r.impliedVolatility) else None,
        }
        for r in hot.itertuples()
    ]


def yoy(values: Sequence[float | None]) -> list[float | None]:
    """Year-over-year growth for an ordered series (oldest first)."""
    out: list[float | None] = [None]
    for prev, cur in pairwise(values):
        out.append(cur / prev - 1 if prev not in (None, 0) and cur is not None else None)
    return out
