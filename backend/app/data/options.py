"""Options market positioning: put/call ratios, implied vol, skew, implied move, max pain.

Primary source is Cboe's free delayed-quote feed (the exchange itself), which
works from cloud servers; Yahoo is a fallback.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd

from ..schemas import DataPacket
from . import _yf
from . import indicators as ind
from .base import clean, get_json, guarded, in_thread, unavailable

SEGMENT = "options"
OCC = re.compile(r"^(?P<root>[A-Z0-9.]+?)(?P<ymd>\d{6})(?P<cp>[CP])(?P<strike>\d{8})$")


def pick_expirations(expirations: list[str], today: date | None = None) -> list[str]:
    """Nearest two expiries plus the first one ~30 and ~90 days out."""
    today = today or datetime.now(UTC).date()
    dated = sorted((e, (date.fromisoformat(e) - today).days) for e in expirations)
    dated = [(e, d) for e, d in dated if d >= 0]
    picks = [e for e, _ in dated[:2]]
    for target in (30, 90):
        later = [e for e, d in dated if d >= target]
        if later and later[0] not in picks:
            picks.append(later[0])
    return picks


def parse_cboe(payload: dict) -> tuple[float | None, dict[str, dict[str, pd.DataFrame]]]:
    """Cboe delayed-quotes JSON -> spot price and {expiration: {"calls": df, "puts": df}}."""
    data = payload.get("data") or {}
    spot = data.get("current_price") or data.get("close")
    chains: dict[str, dict[str, list[dict]]] = {}
    for o in data.get("options") or []:
        m = OCC.match(o.get("option", ""))
        if not m:
            continue
        ymd = m["ymd"]
        exp = f"20{ymd[:2]}-{ymd[2:4]}-{ymd[4:]}"
        bid, ask = o.get("bid") or 0, o.get("ask") or 0
        last = o.get("last_trade_price") or ((bid + ask) / 2 if bid and ask else 0)
        side = "calls" if m["cp"] == "C" else "puts"
        chains.setdefault(exp, {"calls": [], "puts": []})[side].append(
            {
                "strike": int(m["strike"]) / 1000,
                "openInterest": o.get("open_interest") or 0,
                "volume": o.get("volume") or 0,
                "impliedVolatility": o.get("iv"),
                "lastPrice": last,
            }
        )
    frames = {
        e: {
            k: pd.DataFrame(v, columns=["strike", "openInterest", "volume", "impliedVolatility", "lastPrice"])
            for k, v in c.items()
        }
        for e, c in chains.items()
    }
    return (float(spot) if spot else None), frames


def summarize(spot: float, chains: dict[str, dict[str, pd.DataFrame]]) -> dict[str, Any]:
    out: dict[str, Any] = {"spot": spot, "expirations": []}
    for exp in pick_expirations(list(chains)):
        calls, puts = chains[exp]["calls"], chains[exp]["puts"]
        if calls.empty or puts.empty:
            continue
        out["expirations"].append(
            {
                "expiration": exp,
                **ind.chain_summary(calls, puts, spot),
                "unusual": ind.unusual_activity(calls, "call", 3) + ind.unusual_activity(puts, "put", 3),
            }
        )
    return out


def _from_yahoo(ticker: str) -> dict | None:
    t = _yf.ticker(ticker)
    expirations = list(t.options or [])
    if not expirations:
        return None
    spot = float(t.history(period="5d")["Close"].iloc[-1])
    chains = {}
    for exp in pick_expirations(expirations):
        chain = t.option_chain(exp)
        chains[exp] = {"calls": chain.calls, "puts": chain.puts}
    return summarize(spot, chains)


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    notes = ["Delayed snapshot; 'unusual' = volume above open interest and above 500 contracts."]
    try:
        payload = await get_json(f"https://cdn.cboe.com/api/global/delayed_quotes/options/{ticker.upper()}.json")
        spot, chains = parse_cboe(payload)
        if spot and chains:
            data = summarize(spot, chains)
            if data["expirations"]:
                return DataPacket(
                    segment=SEGMENT, ticker=ticker, sources=["Cboe delayed quotes"], notes=notes, data=clean(data)
                )
    except Exception as exc:  # noqa: BLE001 - fall through to Yahoo
        notes.append(f"Cboe feed unavailable ({type(exc).__name__}).")

    data = await in_thread(_from_yahoo, ticker)
    if not data:
        return unavailable(SEGMENT, ticker, "No options data (no listed options, or sources unreachable).")
    return DataPacket(
        segment=SEGMENT, ticker=ticker, sources=["Yahoo Finance option chains"], notes=notes, data=clean(data)
    )
