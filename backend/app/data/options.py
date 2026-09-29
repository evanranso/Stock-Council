"""Options market positioning: put/call ratios, implied vol, skew, implied move, max pain."""

from __future__ import annotations

from datetime import date, datetime

from ..schemas import DataPacket
from . import _yf
from . import indicators as ind
from .base import clean, guarded, in_thread, unavailable

SEGMENT = "options"


def _pick_expirations(expirations: tuple[str, ...]) -> list[str]:
    """Nearest two expiries plus the first one ~30 and ~90 days out."""
    today = date.today()
    dated = [(e, (datetime.strptime(e, "%Y-%m-%d").date() - today).days) for e in expirations]
    picks = [e for e, _ in dated[:2]]
    for target in (30, 90):
        later = [e for e, d in dated if d >= target]
        if later and later[0] not in picks:
            picks.append(later[0])
    return picks


def _collect(ticker: str) -> dict | None:
    t = _yf.ticker(ticker)
    expirations = t.options
    if not expirations:
        return None
    spot = float(t.history(period="5d")["Close"].iloc[-1])
    out = {"spot": spot, "expirations": []}
    for exp in _pick_expirations(expirations):
        chain = t.option_chain(exp)
        out["expirations"].append(
            {
                "expiration": exp,
                **ind.chain_summary(chain.calls, chain.puts, spot),
                "unusual": ind.unusual_activity(chain.calls, "call") + ind.unusual_activity(chain.puts, "put"),
            }
        )
    return out


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    data = await in_thread(_collect, ticker)
    if not data:
        return unavailable(SEGMENT, ticker, "No listed options for this ticker.")
    return DataPacket(
        segment=SEGMENT,
        ticker=ticker,
        sources=["Yahoo Finance option chains (delayed)"],
        notes=["Volume/IV are delayed snapshots; 'unusual' = volume > open interest and > 500 contracts."],
        data=clean(data),
    )
