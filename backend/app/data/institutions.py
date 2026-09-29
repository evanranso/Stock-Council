"""Institutional (13F) and mutual-fund ownership, and who is adding/trimming."""

from __future__ import annotations

from ..schemas import DataPacket
from . import _yf
from .base import clean, df_records, guarded, in_thread, unavailable

SEGMENT = "institutions"


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    major = await in_thread(_yf.safe_attr, ticker, "major_holders")
    inst = await in_thread(_yf.safe_attr, ticker, "institutional_holders")
    funds = await in_thread(_yf.safe_attr, ticker, "mutualfund_holders")
    info = await in_thread(_yf.info, ticker)

    data = {
        "ownership_breakdown": df_records(major),
        "top_institutions": df_records(inst, limit=15),
        "top_mutual_funds": df_records(funds, limit=10),
        "shares_short": info.get("sharesShort"),
        "short_pct_of_float": info.get("shortPercentOfFloat"),
        "short_ratio_days_to_cover": info.get("shortRatio"),
        "shares_short_prior_month": info.get("sharesShortPriorMonth"),
    }
    if not data["top_institutions"]:
        return unavailable(
            SEGMENT,
            ticker,
            "No institutional holder data: the free source (Yahoo) blocks cloud servers. "
            "A paid source such as FMP would enable this analyst.",
        )
    return DataPacket(
        segment=SEGMENT,
        ticker=ticker,
        sources=["Yahoo Finance (13F-derived)"],
        notes=["13F filings lag the quarter end by up to 45 days."],
        data=clean(data),
    )
