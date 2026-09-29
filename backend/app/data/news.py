"""Recent company news headlines and summaries."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from ..schemas import DataPacket
from . import _yf
from .base import finnhub, guarded, in_thread, unavailable

SEGMENT = "news"


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    try:
        start = (date.today() - timedelta(days=21)).isoformat()
        rows = await finnhub("company-news", symbol=ticker, **{"from": start, "to": date.today().isoformat()})
        items = [
            {
                "date": datetime.fromtimestamp(r["datetime"], tz=UTC).date().isoformat(),
                "source": r.get("source"),
                "headline": r.get("headline"),
                "summary": (r.get("summary") or "")[:500],
            }
            for r in rows[:40]
        ]
        if items:
            return DataPacket(
                segment=SEGMENT, ticker=ticker, sources=["Finnhub company news"], data={"articles": items}
            )
    except RuntimeError:
        pass  # no key: fall back

    raw = await in_thread(_yf.safe_attr, ticker, "news") or []
    items = []
    for r in raw[:25]:
        c = r.get("content", r)
        items.append(
            {
                "date": (c.get("pubDate") or "")[:10],
                "source": (c.get("provider") or {}).get("displayName")
                if isinstance(c.get("provider"), dict)
                else c.get("publisher"),
                "headline": c.get("title"),
                "summary": (c.get("summary") or "")[:500],
            }
        )
    if not items:
        return unavailable(SEGMENT, ticker, "No recent news found.")
    return DataPacket(
        segment=SEGMENT, ticker=ticker, status="partial", sources=["Yahoo Finance news"], data={"articles": items}
    )
