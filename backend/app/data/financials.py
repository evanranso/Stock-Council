"""Financial statements from SEC XBRL filings, plus valuation multiples."""

from __future__ import annotations

from ..schemas import DataPacket
from . import _yf, sec
from . import indicators as ind
from .base import clean, guarded, in_thread, unavailable

SEGMENT = "financials"

# First concept found wins; companies tag the same line item differently.
CONCEPTS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "stockholders_equity": ["StockholdersEquity"],
    "diluted_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}


def _annual_series(facts: dict, names: list[str]) -> dict[str, float]:
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for name in names:
        units = gaap.get(name, {}).get("units", {})
        rows = next(iter(units.values()), [])
        by_year: dict[str, float] = {}
        for r in rows:
            if (
                r.get("form") == "10-K"
                and r.get("fp") == "FY"
                and r.get("frame", "").startswith("CY")
                and len(r["frame"]) == 6
            ):
                by_year[r["frame"][2:]] = r["val"]
        if by_year:
            return dict(sorted(by_year.items())[-5:])
    return {}


def _build_table(facts: dict) -> dict:
    series = {k: _annual_series(facts, v) for k, v in CONCEPTS.items()}
    years = sorted({y for s in series.values() for y in s})[-5:]
    table = {k: [s.get(y) for y in years] for k, s in series.items()}

    def ratio(a: str, b: str) -> list:
        return [x / y if x is not None and y else None for x, y in zip(table[a], table[b], strict=True)]

    fcf = [
        o - c if o is not None and c is not None else None
        for o, c in zip(table["operating_cash_flow"], table["capex"], strict=True)
    ]
    return {
        "fiscal_years": years,
        "values_usd": table,
        "derived": {
            "revenue_growth_yoy": ind.yoy(table["revenue"]),
            "gross_margin": ratio("gross_profit", "revenue"),
            "operating_margin": ratio("operating_income", "revenue"),
            "net_margin": ratio("net_income", "revenue"),
            "free_cash_flow": fcf,
            "share_count_change_yoy": ind.yoy(table["diluted_shares"]),
        },
    }


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    info = await in_thread(_yf.info, ticker)
    valuation = {
        k: info.get(k)
        for k in [
            "marketCap",
            "enterpriseValue",
            "trailingPE",
            "forwardPE",
            "priceToSalesTrailing12Months",
            "priceToBook",
            "enterpriseToEbitda",
            "pegRatio",
            "dividendYield",
            "payoutRatio",
        ]
    }
    ttm = {
        k: info.get(k)
        for k in [
            "totalRevenue",
            "revenueGrowth",
            "grossMargins",
            "operatingMargins",
            "profitMargins",
            "freeCashflow",
            "totalCash",
            "totalDebt",
            "debtToEquity",
            "currentRatio",
            "returnOnEquity",
        ]
    }
    data: dict = {"valuation": valuation, "trailing_twelve_months": ttm}
    sources, notes = ["Yahoo Finance (valuation, TTM)"], []

    cik = await sec.cik_for(ticker)
    if cik:
        data["annual_from_10k"] = _build_table(await sec.company_facts(cik))
        sources.append("SEC EDGAR XBRL company facts")
    else:
        notes.append("No SEC CIK found (foreign issuer or ETF?); annual history omitted.")

    if not cik and not info:
        return unavailable(SEGMENT, ticker, "No financial data found.")
    return DataPacket(
        segment=SEGMENT,
        ticker=ticker,
        status="ok" if cik else "partial",
        sources=sources,
        notes=notes,
        data=clean(data),
    )
