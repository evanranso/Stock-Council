"""Insider (Form 4) transactions, separating open-market buys/sells from grants and option exercises."""

from __future__ import annotations

from datetime import date, timedelta

from ..schemas import DataPacket
from . import _yf
from .base import clean, df_records, finnhub, guarded, in_thread, unavailable

SEGMENT = "insiders"

# SEC Form 4 transaction codes worth distinguishing.
CODES = {
    "P": "open-market purchase",
    "S": "open-market sale",
    "A": "grant/award",
    "M": "option exercise",
    "F": "tax withholding",
    "G": "gift",
    "D": "disposition to issuer",
}


def _summarize(rows: list[dict], days: int) -> dict:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    window = [r for r in rows if (r.get("transactionDate") or "") >= cutoff]
    buys = [r for r in window if r.get("transactionCode") == "P"]
    sells = [r for r in window if r.get("transactionCode") == "S"]

    def value(rs: list[dict]) -> float:
        return sum(abs(r.get("change") or 0) * (r.get("transactionPrice") or 0) for r in rs)

    return {
        "open_market_buys": len(buys),
        "open_market_sells": len(sells),
        "buy_value_usd": value(buys),
        "sell_value_usd": value(sells),
        "distinct_buyers": sorted({r["name"] for r in buys}),
        "distinct_sellers": sorted({r["name"] for r in sells}),
    }


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    try:
        start = (date.today() - timedelta(days=365)).isoformat()
        rows = (await finnhub("stock/insider-transactions", symbol=ticker, **{"from": start})).get("data", [])
        rows.sort(key=lambda r: r.get("transactionDate") or "", reverse=True)
        data = {
            "summary_90d": _summarize(rows, 90),
            "summary_12m": _summarize(rows, 365),
            "transaction_code_legend": CODES,
            "transactions": [
                {
                    k: r.get(k)
                    for k in ("name", "transactionDate", "transactionCode", "change", "share", "transactionPrice")
                }
                for r in rows[:60]
            ],
        }
        return DataPacket(segment=SEGMENT, ticker=ticker, sources=["Finnhub (SEC Form 4)"], data=clean(data))
    except RuntimeError:
        pass  # no Finnhub key; fall back to yfinance

    tx = await in_thread(_yf.safe_attr, ticker, "insider_transactions")
    purchases = await in_thread(_yf.safe_attr, ticker, "insider_purchases")
    if tx is None or tx.empty:
        return unavailable(SEGMENT, ticker, "No insider transaction data (set FINNHUB_API_KEY for better coverage).")
    return DataPacket(
        segment=SEGMENT,
        ticker=ticker,
        status="partial",
        sources=["Yahoo Finance"],
        notes=["Fallback source; transaction codes not normalized."],
        data={"six_month_summary": df_records(purchases), "transactions": df_records(tx, limit=60)},
    )
