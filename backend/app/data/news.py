"""Recent company news: Finnhub when keyed, otherwise public RSS feeds (Yahoo, then Google News)."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from ..schemas import DataPacket
from . import sec
from .base import finnhub, get_text, guarded, unavailable

SEGMENT = "news"
DAYS = 21
MAX_ARTICLES = 40


def _clean(text: str | None, limit: int = 500) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def parse_rss(xml: str, days: int = DAYS, now: datetime | None = None) -> list[dict]:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    items = []
    for item in ET.fromstring(xml).iter("item"):
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        if published < cutoff:
            continue
        items.append(
            {
                "date": published.date().isoformat(),
                "source": item.findtext("source") or None,
                "headline": _clean(item.findtext("title"), 300),
                "summary": _clean(item.findtext("description")),
            }
        )
    items.sort(key=lambda a: a["date"], reverse=True)
    return items[:MAX_ARTICLES]


async def _finnhub(ticker: str) -> list[dict]:
    today = datetime.now(UTC).date()
    rows = await finnhub(
        "company-news", symbol=ticker, **{"from": (today - timedelta(days=DAYS)).isoformat(), "to": today.isoformat()}
    )
    return [
        {
            "date": datetime.fromtimestamp(r["datetime"], tz=UTC).date().isoformat(),
            "source": r.get("source"),
            "headline": r.get("headline"),
            "summary": (r.get("summary") or "")[:500],
        }
        for r in rows[:MAX_ARTICLES]
    ]


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    notes: list[str] = []
    try:
        items = await _finnhub(ticker)
        if items:
            return DataPacket(
                segment=SEGMENT, ticker=ticker, sources=["Finnhub company news"], data={"articles": items}
            )
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Finnhub news unavailable ({exc}).")

    company = None
    try:
        company = await sec.company_info(ticker)
    except Exception:  # noqa: BLE001
        pass
    query = quote_plus(f'"{(company or {}).get("name") or ticker}" OR {ticker} stock')
    feeds = [
        ("Yahoo Finance RSS", f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"),
        ("Google News RSS", f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"),
    ]
    for name, url in feeds:
        try:
            items = parse_rss(await get_text(url))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{name} unavailable ({type(exc).__name__}).")
            continue
        if items:
            return DataPacket(
                segment=SEGMENT,
                ticker=ticker,
                status="partial",
                sources=[name],
                notes=[*notes, "Headlines only from RSS; add FINNHUB_API_KEY for article summaries."],
                data={"articles": items},
            )
    return unavailable(SEGMENT, ticker, "No recent news found. " + " ".join(notes))
