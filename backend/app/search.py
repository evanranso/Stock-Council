"""Ticker / company-name lookup over every SEC-registered listed company.

The SEC's list is ordered roughly by company size, so that order is used as the
tie-breaker: typing "apple" puts Apple Inc. above smaller "Apple..." names.
"""

from __future__ import annotations

import re
import time
from typing import Any

from .data.base import get_json, sec_headers

_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_REFRESH_SECONDS = 24 * 3600
_MAJOR_EXCHANGES = {"Nasdaq", "NYSE", "CBOE", "NYSE American", "NYSE Arca"}
_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|holdings?|group|sa|nv|ag|the)\b"
)

_index: list[dict[str, Any]] = []
_loaded_at = 0.0


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


async def _load() -> list[dict[str, Any]]:
    try:
        raw = await get_json(_EXCHANGE_URL, headers=sec_headers())
        fields = raw["fields"]
        return build_index([dict(zip(fields, row, strict=False)) for row in raw["data"]])
    except Exception:  # noqa: BLE001 - fall back to the simpler list (no exchange field)
        raw = await get_json(_TICKERS_URL, headers=sec_headers())
        return build_index([{"ticker": r["ticker"], "name": r["title"]} for r in raw.values()])


async def search(query: str, limit: int = 8) -> list[dict[str, Any]]:
    global _index, _loaded_at
    if not _index or time.time() - _loaded_at > _REFRESH_SECONDS:
        _index = await _load()
        _loaded_at = time.time()
    return rank_matches(_index, query, limit)
