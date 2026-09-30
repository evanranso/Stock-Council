"""Ticker / company-name lookup over every SEC-registered listed company.

The SEC's list is ordered roughly by company size, so that order is used as the
tie-breaker: typing "apple" puts Apple Inc. above smaller "Apple..." names.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from .data.base import get_json, get_text, sec_headers

log = logging.getLogger(__name__)

_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# Backup list if the SEC blocks or throttles the server (it rate-limits cloud hosts).
_NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
_NASDAQ_EXCHANGES = {"Q": "Nasdaq", "N": "NYSE", "A": "NYSE American", "P": "NYSE Arca", "Z": "CBOE"}
_REFRESH_SECONDS = 24 * 3600
_RETRY_AFTER_FAILURE = 120
_MAJOR_EXCHANGES = {"Nasdaq", "NYSE", "CBOE", "NYSE American", "NYSE Arca"}
_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|holdings?|group|sa|nv|ag|the)\b"
)

_index: list[dict[str, Any]] = []
_loaded_at = 0.0
_failed_at = 0.0
_lock = asyncio.Lock()


def normalize(text: str) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    text = _SUFFIXES.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_index(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for rank, r in enumerate(rows):
        ticker = (r.get("ticker") or "").upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        out.append(
            {
                "ticker": ticker,
                "name": r.get("name") or "",
                "exchange": r.get("exchange"),
                "rank": rank,
                "_norm": normalize(r.get("name") or ""),
            }
        )
    return out


def rank_matches(index: list[dict[str, Any]], query: str, limit: int = 8) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []
    qt, qn = q.upper(), normalize(q)
    scored = []
    for row in index:
        t, n = row["ticker"], row["_norm"]
        if t == qt:
            score = 0
        elif qn and n == qn:
            score = 1
        elif t.startswith(qt):
            score = 2
        elif qn and n.startswith(qn):
            score = 3
        elif qn and re.search(rf"\b{re.escape(qn)}", n):
            score = 4
        else:
            continue
        minor = 0 if row["exchange"] in _MAJOR_EXCHANGES or row["exchange"] is None else 1
        scored.append((score, minor, row["rank"], row))
    scored.sort(key=lambda s: s[:3])
    return [{k: v for k, v in s[3].items() if not k.startswith("_") and k != "rank"} for s in scored[:limit]]


def parse_nasdaq(text: str) -> list[dict[str, Any]]:
    """Nasdaq Trader's pipe-delimited list of every US-listed symbol (stocks only, no ETFs or test issues)."""
    lines = text.splitlines()
    if not lines:
        return []
    cols = lines[0].split("|")
    rows = []
    for line in lines[1:]:
        r = dict(zip(cols, line.split("|"), strict=False))
        if r.get("Test Issue") != "N" or r.get("ETF") == "Y" or not r.get("Symbol"):
            continue
        name = (r.get("Security Name") or "").split(" - ")[0].strip()
        rows.append(
            {"ticker": r["Symbol"], "name": name, "exchange": _NASDAQ_EXCHANGES.get(r.get("Listing Exchange", ""))}
        )
    return rows


async def _load() -> list[dict[str, Any]]:
    try:
        raw = await get_json(_EXCHANGE_URL, headers=sec_headers())
        fields = raw["fields"]
        return build_index([dict(zip(fields, row, strict=False)) for row in raw["data"]])
    except Exception as exc:  # noqa: BLE001 - try the next source
        log.warning("Search: SEC exchange list failed (%s)", exc)
    try:
        raw = await get_json(_TICKERS_URL, headers=sec_headers())
        return build_index([{"ticker": r["ticker"], "name": r["title"]} for r in raw.values()])
    except Exception as exc:  # noqa: BLE001
        log.warning("Search: SEC ticker list failed (%s)", exc)
    rows = parse_nasdaq(await get_text(_NASDAQ_URL))
    if not rows:
        raise RuntimeError("Nasdaq symbol list was empty")
    return build_index(rows)


async def ensure_index() -> list[dict[str, Any]]:
    """Load the company list once (one download at a time), refresh daily, and back off after a failure."""
    global _index, _loaded_at, _failed_at

    def settled() -> bool:
        fresh = bool(_index) and time.time() - _loaded_at < _REFRESH_SECONDS
        return fresh or time.time() - _failed_at < _RETRY_AFTER_FAILURE

    if settled():
        return _index
    async with _lock:
        if settled():  # another search just loaded it (or just failed): don't download again
            return _index
        try:
            _index = await _load()
            _loaded_at = time.time()
        except Exception as exc:  # noqa: BLE001 - keep serving the old list (or none) and retry later
            _failed_at = time.time()
            log.warning("Search: couldn't load any company list (%s)", exc)
    return _index


async def search(query: str, limit: int = 8) -> list[dict[str, Any]]:
    return rank_matches(await ensure_index(), query, limit)
