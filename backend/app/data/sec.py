"""SEC EDGAR helpers (free, no key; requires a descriptive User-Agent)."""

from __future__ import annotations

import html
import re

from .base import get_json, get_text, sec_headers

_cik_map: dict[str, int] | None = None


async def cik_for(ticker: str) -> int | None:
    global _cik_map
    if _cik_map is None:
        raw = await get_json("https://www.sec.gov/files/company_tickers.json", headers=sec_headers())
        _cik_map = {row["ticker"].upper(): int(row["cik_str"]) for row in raw.values()}
    return _cik_map.get(ticker.upper().replace("-", ".")) or _cik_map.get(ticker.upper())


async def company_facts(cik: int) -> dict:
    return await get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", headers=sec_headers())


async def submissions(cik: int) -> dict:
    return await get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=sec_headers())


async def document_text(cik: int, accession: str, primary_doc: str) -> str:
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{primary_doc}"
    return html_to_text(await get_text(url, headers=sec_headers()))


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
