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
MAX_ARTICLES = 40  # fetched
SHOWN = 20  # given to the analyst, after removing repeats
SUMMARY_CHARS = 280


def _clean(text: str | None, limit: int = SUMMARY_CHARS) -> str:
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
            "summary": _clean(r.get("summary")),
        }
        for r in rows[:MAX_ARTICLES]
    ]


def _key(headline: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (headline or "").lower()).strip()[:60]


_SUFFIX = {
    "com",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "co",
    "company",
    "ltd",
    "plc",
    "holdings",
    "group",
    "the",
}


def short_name(company: str | None) -> str:
    """'AMAZON COM INC' -> 'amazon', 'First Solar, Inc.' -> 'first solar'."""
    words = re.sub(r"[^a-z0-9 ]+", " ", (company or "").lower()).split()
    return " ".join(w for w in words if w not in _SUFFIX)


def curate(articles: list[dict], ticker: str, company: str | None, limit: int = SHOWN) -> list[dict]:
    """Drop repeats of the same story, prefer articles about this company over market roundups, newest first."""
    seen: set[str] = set()
    unique = []
    for a in articles:
        k = _key(a.get("headline") or "")
        if k and k not in seen:
            seen.add(k)
            unique.append(a)
    names = [n for n in {ticker.lower(), short_name(company)} if len(n) >= 2]

    def about(a: dict) -> bool:
        text = f"{a.get('headline') or ''} {a.get('summary') or ''}".lower()
        return any(re.search(rf"\b{re.escape(n)}\b", text) for n in names)

    picked = [a for a in unique if about(a)][:limit]
    picked += [a for a in unique if not about(a)][: limit - len(picked)]
    for a in picked:
        if not a.get("summary") or _key(a["summary"]).startswith(_key(a.get("headline") or "")[:40]):
            a.pop("summary", None)  # RSS summaries often just repeat the headline
    return sorted(picked, key=lambda a: a.get("date") or "", reverse=True)


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    notes: list[str] = []
    company = None
    try:
        company = await sec.company_info(ticker)
    except Exception:  # noqa: BLE001
        pass
    name = (company or {}).get("name")
    try:
        items = await _finnhub(ticker)
        if items:
            return DataPacket(
                segment=SEGMENT,
                ticker=ticker,
                sources=["Finnhub company news"],
                data={"articles": curate(items, ticker, name), "articles_found_21d": len(items)},
            )
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Finnhub news unavailable ({exc}).")

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
                data={"articles": curate(items, ticker, name), "articles_found_21d": len(items)},
            )
    return unavailable(SEGMENT, ticker, "No recent news found. " + " ".join(notes))
