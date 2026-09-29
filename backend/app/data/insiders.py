"""Insider trades parsed directly from SEC Form 4 filings (free, no key, works from cloud servers).

Separates open-market buys/sells (the real signal) from grants, option
exercises, tax withholding and gifts, and flags pre-planned 10b5-1 trades.
"""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from typing import Any

from ..schemas import DataPacket
from . import sec
from .base import clean, guarded, unavailable

SEGMENT = "insiders"
MAX_FILINGS = 60

CODES = {
    "P": "open-market purchase",
    "S": "open-market sale",
    "A": "grant/award",
    "M": "option exercise",
    "F": "tax withholding",
    "G": "gift",
    "D": "disposition to issuer",
    "C": "conversion",
}


def _text(node: ET.Element | None, path: str) -> str | None:
    found = node.find(path) if node is not None else None
    if found is None:
        return None
    text = (found.text or "").strip()
    return text or None


def _num(node: ET.Element | None, path: str) -> float | None:
    value = _text(node, path)
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def parse_form4(xml: str) -> list[dict[str, Any]]:
    """Non-derivative transactions from one Form 4 XML document."""
    root = ET.fromstring(re.sub(r"\sxmlns(:\w+)?=\"[^\"]+\"", "", xml, count=1))
    owner = root.find("reportingOwner")
    name = _text(owner, "reportingOwnerId/rptOwnerName")
    rel = owner.find("reportingOwnerRelationship") if owner is not None else None
    roles = []
    if _text(rel, "isDirector") in ("1", "true"):
        roles.append("director")
    if _text(rel, "isOfficer") in ("1", "true"):
        roles.append(_text(rel, "officerTitle") or "officer")
    if _text(rel, "isTenPercentOwner") in ("1", "true"):
        roles.append("10% owner")
    planned = _text(root, "aff10b5One") in ("1", "true")

    out = []
    for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        shares = _num(tx, "transactionAmounts/transactionShares/value")
        direction = _text(tx, "transactionAmounts/transactionAcquiredDisposedCode/value")
        out.append(
            {
                "name": name,
                "role": ", ".join(roles) or None,
                "date": _text(tx, "transactionDate/value"),
                "code": _text(tx, "transactionCoding/transactionCode"),
                "shares": -shares if shares is not None and direction == "D" else shares,
                "price": _num(tx, "transactionAmounts/transactionPricePerShare/value"),
                "shares_owned_after": _num(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"),
                "planned_10b5_1": planned,
            }
        )
    return out


def summarize(rows: list[dict], days: int, today: datetime | None = None) -> dict[str, Any]:
    cutoff = ((today or datetime.now(UTC)) - timedelta(days=days)).date().isoformat()
    window = [r for r in rows if (r.get("date") or "") >= cutoff]
    buys = [r for r in window if r["code"] == "P"]
    sells = [r for r in window if r["code"] == "S"]

    def value(rs: list[dict]) -> float:
        return sum(abs(r["shares"] or 0) * (r["price"] or 0) for r in rs)

    return {
        "open_market_buys": len(buys),
        "open_market_sells": len(sells),
        "buy_value_usd": value(buys),
        "sell_value_usd": value(sells),
        "sells_under_10b5_1_plans": sum(r["planned_10b5_1"] for r in sells),
        "distinct_buyers": sorted({r["name"] for r in buys if r["name"]}),
        "distinct_sellers": sorted({r["name"] for r in sells if r["name"]}),
    }


def _xml_document(primary: str) -> str:
    # EDGAR lists the styled view ("xslF345X05/form4.xml"); the raw XML is the same file without the prefix.
    return primary.split("/", 1)[1] if primary.startswith("xsl") and "/" in primary else primary


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    cik = await sec.cik_for(ticker)
    if not cik:
        return unavailable(SEGMENT, ticker, "No SEC filer found for this ticker.")
    subs = await sec.submissions(cik)
    cutoff = (datetime.now(UTC) - timedelta(days=365)).date().isoformat()
    filings = [r for r in sec.recent_filings(subs) if r["form"] == "4" and r["filingDate"] >= cutoff][:MAX_FILINGS]
    if not filings:
        return unavailable(SEGMENT, ticker, "No Form 4 insider filings in the last 12 months.")

    async def load(f: dict) -> list[dict]:
        try:
            return parse_form4(await sec.raw_document(cik, f["accessionNumber"], _xml_document(f["primaryDocument"])))
        except Exception:  # noqa: BLE001 - skip unparseable filings, keep the rest
            return []

    rows = [tx for batch in await asyncio.gather(*(load(f) for f in filings)) for tx in batch]
    rows.sort(key=lambda r: r.get("date") or "", reverse=True)
    data = {
        "summary_90d": summarize(rows, 90),
        "summary_12m": summarize(rows, 365),
        "transaction_code_legend": CODES,
        "form4_filings_read": len(filings),
        "transactions": rows[:80],
    }
    return DataPacket(
        segment=SEGMENT,
        ticker=ticker,
        sources=["SEC EDGAR Form 4 filings"],
        notes=["Open-market purchases (P) are the strongest signal; 10b5-1 sales are pre-planned and weaker."],
        data=clean(data),
    )
