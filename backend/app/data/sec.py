"""SEC EDGAR helpers (free, no key; requires a descriptive User-Agent).

EDGAR is the most reliable free source from cloud servers, so the council leans
on it: company identity, financial statements (XBRL), filings text, and Form 4
insider trades all come from here.
"""

from __future__ import annotations

import asyncio
import html
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from .base import get_json, get_text, sec_headers

_cik_map: dict[str, int] | None = None
_cache: dict[str, tuple[float, Any]] = {}
_CACHE_SECONDS = 3600
# SEC fair-access policy: at most 10 requests/second per client.
_limit = asyncio.Semaphore(5)


async def _cached(key: str, loader: Callable[[], Awaitable[Any]]) -> Any:
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _CACHE_SECONDS:
        return hit[1]
    value = await loader()
    _cache[key] = (time.time(), value)
    return value


async def _get_json(url: str) -> Any:
    async with _limit:
        return await get_json(url, headers=sec_headers())


async def _get_text(url: str) -> str:
    async with _limit:
        return await get_text(url, headers=sec_headers())


async def cik_for(ticker: str) -> int | None:
    global _cik_map
    if _cik_map is None:
        raw = await _get_json("https://www.sec.gov/files/company_tickers.json")
        _cik_map = {row["ticker"].upper(): int(row["cik_str"]) for row in raw.values()}
    t = ticker.upper()
    return _cik_map.get(t) or _cik_map.get(t.replace("-", ".")) or _cik_map.get(t.replace(".", "-"))


async def company_facts(cik: int) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    return await _cached(url, lambda: _get_json(url))


async def submissions(cik: int) -> dict:
    url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
    return await _cached(url, lambda: _get_json(url))


def recent_filings(subs: dict) -> list[dict]:
    """Newest-first list of filing rows from a submissions payload."""
    recent = subs["filings"]["recent"]
    return [dict(zip(recent.keys(), vals, strict=True)) for vals in zip(*recent.values(), strict=True)]


def archive_url(cik: int, accession: str, document: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{document}"


async def document_text(cik: int, accession: str, primary_doc: str) -> str:
    return html_to_text(await _get_text(archive_url(cik, accession, primary_doc)))


async def raw_document(cik: int, accession: str, document: str) -> str:
    return await _get_text(archive_url(cik, accession, document))


async def company_info(ticker: str) -> dict[str, Any] | None:
    """Name, industry and fiscal calendar straight from EDGAR (no Yahoo needed)."""
    cik = await cik_for(ticker)
    if not cik:
        return None
    subs = await submissions(cik)
    sic = int(subs["sic"]) if str(subs.get("sic") or "").isdigit() else None
    return {
        "cik": cik,
        "name": subs.get("name"),
        "sic": sic,
        "industry": subs.get("sicDescription"),
        "sector": sector_for_sic(sic),
        "fiscal_year_end_mmdd": subs.get("fiscalYearEnd"),
        "exchanges": subs.get("exchanges"),
    }


# SIC code ranges -> SPDR sector ETF name, most specific first.
_SIC_SECTORS: list[tuple[int, int, str]] = [
    (6798, 6798, "Real Estate"),
    (3570, 3579, "Technology"),
    (3660, 3679, "Technology"),
    (3810, 3829, "Technology"),
    (7370, 7379, "Technology"),
    (2830, 2836, "Healthcare"),
    (3840, 3851, "Healthcare"),
    (8000, 8099, "Healthcare"),
    (3710, 3716, "Consumer Cyclical"),
    (2000, 2199, "Consumer Defensive"),
    (5400, 5499, "Consumer Defensive"),
    (2840, 2844, "Consumer Defensive"),
    (1300, 1399, "Energy"),
    (2900, 2999, "Energy"),
    (4900, 4949, "Utilities"),
    (4800, 4899, "Communication Services"),
    (7810, 7819, "Communication Services"),
    (2700, 2799, "Communication Services"),
    (6000, 6799, "Financial Services"),
    (5000, 5999, "Consumer Cyclical"),
    (7000, 7999, "Consumer Cyclical"),
    (1000, 1499, "Basic Materials"),
    (2800, 2899, "Basic Materials"),
    (3300, 3399, "Basic Materials"),
    (3720, 3729, "Industrials"),
    (3400, 3569, "Industrials"),
    (3580, 3659, "Industrials"),
    (4000, 4799, "Industrials"),
    (1500, 1799, "Industrials"),
]


def sector_for_sic(sic: int | None) -> str | None:
    if sic is None:
        return None
    return next((name for lo, hi, name in _SIC_SECTORS if lo <= sic <= hi), None)


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|ix:header).*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def section(text: str, start_patterns: list[str], end_patterns: list[str], max_chars: int) -> str | None:
    """Pull a section (e.g. Risk Factors) out of a filing's plain text.

    Filings mention section titles in the table of contents first, so take the
    *last* strong match of the start heading that is followed by real content.
    """
    starts = [m.start() for p in start_patterns for m in re.finditer(p, text, re.IGNORECASE)]
    for start in sorted(starts, reverse=True):
        rest = text[start:]
        ends = [m.start() for p in end_patterns for m in re.finditer(p, rest[200:], re.IGNORECASE)]
        end = (min(ends) + 200) if ends else len(rest)
        if end > 2000:  # skip table-of-contents hits
            return rest[: min(end, max_chars)]
    return None
