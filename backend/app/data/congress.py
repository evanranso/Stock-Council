"""Congressional stock trades (STOCK Act disclosures).

There is no reliable *free* API for this. Finnhub exposes it on paid plans;
Quiver Quantitative and FMP are other paid options. This adapter tries Finnhub
and otherwise reports the gap honestly so the analyst stays neutral.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..schemas import DataPacket
from .base import clean, finnhub, guarded, unavailable

SEGMENT = "congress"


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    start = (date.today() - timedelta(days=365)).isoformat()
    try:
        raw = await finnhub(
            "stock/congressional-trading", symbol=ticker, **{"from": start, "to": date.today().isoformat()}
        )
    except Exception as exc:  # noqa: BLE001
        return unavailable(SEGMENT, ticker, f"Congress trading data needs a paid data plan (Finnhub/Quiver/FMP): {exc}")

    rows = raw.get("data", [])
    trades = [
        {
            k: r.get(k)
            for k in (
                "name",
                "position",
                "transactionDate",
                "filingDate",
                "transactionType",
                "amountFrom",
                "amountTo",
                "ownerType",
            )
        }
        for r in rows
    ]
    buys = [t for t in trades if "purchase" in (t["transactionType"] or "").lower()]
    sells = [t for t in trades if "sale" in (t["transactionType"] or "").lower()]
    data = {
        "trades_last_12m": len(trades),
        "purchases": len(buys),
        "sales": len(sells),
        "distinct_members": sorted({t["name"] for t in trades if t["name"]}),
        "trades": trades[:50],
    }
    return DataPacket(
        segment=SEGMENT,
        ticker=ticker,
        sources=["Finnhub (STOCK Act disclosures)"],
        notes=["Disclosures can lag trades by up to 45 days; amounts are reported as ranges."],
        data=clean(data),
    )
