"""Financial statements from SEC XBRL: latest quarters, trailing twelve months, balance sheet, and valuation.

Everything comes from the company's own filings (through the most recent
10-Q), so the view is as current as the latest report. Valuation multiples are
computed here from the latest price and SEC share count instead of relying on
Yahoo's summary endpoint, which blocks most cloud servers.
"""

from __future__ import annotations

from typing import Any

from ..schemas import DataPacket
from . import _yf, sec, xbrl
from .base import clean, guarded, in_thread, unavailable

SEGMENT = "financials"

# Candidate tags per line item; the one with the most recent data wins.
FLOWS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "rnd": ["ResearchAndDevelopmentExpense"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "diluted_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}
STOCKS = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "marketable_securities_current": ["MarketableSecuritiesCurrent", "ShortTermInvestments"],
    "marketable_securities_noncurrent": ["MarketableSecuritiesNoncurrent", "LongTermInvestments"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "current_debt": ["LongTermDebtCurrent", "DebtCurrent"],
    "commercial_paper": ["CommercialPaper"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
}
QUARTERS_SHOWN = 8
YEARS_SHOWN = 5


def _ratio(a: float | None, b: float | None) -> float | None:
    return a / b if a is not None and b else None


def build_financials(facts: dict) -> dict[str, Any]:
    q_series: dict[str, list[dict]] = {}
    a_series: dict[str, list[dict]] = {}
    used_tags: dict[str, str] = {}
    for key, tags in FLOWS.items():
        tag, rows = xbrl.concept_rows(facts, tags)
        if tag:
            used_tags[key] = tag
        q_series[key] = xbrl.quarterly(rows)
        a_series[key] = xbrl.annual(rows)

    # --- Quarterly table, aligned on revenue's quarter ends (fallback: net income) ---
    anchor = q_series["revenue"] or q_series["net_income"]
    ends = [q["end"] for q in anchor][-QUARTERS_SHOWN:]
    quarterly: dict[str, Any] = {"period_ends": ends}
    for key in FLOWS:
        by_end = {q["end"]: q["val"] for q in q_series[key]}
        quarterly[key] = [by_end.get(e) for e in ends]
    quarterly["revenue_growth_yoy"] = [
        xbrl.growth(v, xbrl.value_near(q_series["revenue"], xbrl.year_ago(e)))
        for e, v in zip(ends, quarterly["revenue"], strict=True)
    ]
    quarterly["eps_growth_yoy"] = [
        xbrl.growth(v, xbrl.value_near(q_series["eps_diluted"], xbrl.year_ago(e)))
        for e, v in zip(ends, quarterly["eps_diluted"], strict=True)
    ]
    for name, num in (
        ("gross_margin", "gross_profit"),
        ("operating_margin", "operating_income"),
        ("net_margin", "net_income"),
    ):
        quarterly[name] = [_ratio(n, r) for n, r in zip(quarterly[num], quarterly["revenue"], strict=True)]
    quarterly["free_cash_flow"] = [
        o - c if o is not None and c is not None else None
        for o, c in zip(quarterly["operating_cash_flow"], quarterly["capex"], strict=True)
    ]

    # --- Trailing twelve months ---
    ttm = {key: (xbrl.ttm(q_series[key]) or {}).get("val") for key in FLOWS if key != "diluted_shares"}
    ttm_end = (xbrl.ttm(anchor) or {}).get("end")
    ttm["period_end"] = ttm_end
    if ttm.get("operating_cash_flow") is not None and ttm.get("capex") is not None:
        ttm["free_cash_flow"] = ttm["operating_cash_flow"] - ttm["capex"]
    ttm["gross_margin"] = _ratio(ttm.get("gross_profit"), ttm.get("revenue"))
    ttm["operating_margin"] = _ratio(ttm.get("operating_income"), ttm.get("revenue"))
    ttm["net_margin"] = _ratio(ttm.get("net_income"), ttm.get("revenue"))
    if ttm_end:
        prior = [q for q in anchor if q["end"] <= xbrl.year_ago(ttm_end)]
        prior_ttm = xbrl.ttm(prior) if prior else None
        ttm["revenue_growth_vs_prior_ttm"] = xbrl.growth(ttm.get("revenue"), (prior_ttm or {}).get("val"))

    # --- Annual (fiscal years) ---
    a_anchor = a_series["revenue"] or a_series["net_income"]
    a_ends = [y["end"] for y in a_anchor][-YEARS_SHOWN:]
    annual: dict[str, Any] = {"fiscal_year_ends": a_ends}
    for key in ("revenue", "operating_income", "net_income", "eps_diluted", "operating_cash_flow", "capex"):
        by_end = {y["end"]: y["val"] for y in a_series[key]}
        annual[key] = [by_end.get(e) for e in a_ends]

    # --- Balance sheet: latest point plus the same point a year earlier ---
    balance: dict[str, Any] = {}
    latest_bs_end = None
    for key, tags in STOCKS.items():
        _, rows = xbrl.concept_rows(facts, tags)
        points = xbrl.instants(rows)
        if points:
            latest = points[-1]
            latest_bs_end = max(latest_bs_end or "", latest["end"])
            balance[key] = {
                "as_of": latest["end"],
                "value": latest["val"],
                "year_ago": xbrl.value_near(points, xbrl.year_ago(latest["end"]), 45),
            }
    debt = sum((balance.get(k) or {}).get("value") or 0 for k in ("long_term_debt", "current_debt", "commercial_paper"))
    cash_like = sum(
        (balance.get(k) or {}).get("value") or 0
        for k in ("cash", "marketable_securities_current", "marketable_securities_noncurrent")
    )
    derived_bs = {
        "total_debt": debt or None,
        "cash_and_investments": cash_like or None,
        "net_cash": (cash_like - debt) if (cash_like or debt) else None,
        "current_ratio": _ratio(
            (balance.get("current_assets") or {}).get("value"), (balance.get("current_liabilities") or {}).get("value")
        ),
    }

    _, share_rows = xbrl.concept_rows(facts, ["EntityCommonStockSharesOutstanding"], taxonomy="dei")
    share_points = xbrl.instants(share_rows)
    return {
        "latest_quarter_end": ends[-1] if ends else None,
        "trailing_twelve_months": ttm,
        "quarterly_last_8": quarterly,
        "annual_last_5": annual,
        "balance_sheet": {"as_of": latest_bs_end, **balance, "derived": derived_bs},
        "shares_outstanding": share_points[-1] if share_points else None,
        "xbrl_tags_used": used_tags,
    }


def valuation(fin: dict, price: float | None) -> dict[str, Any]:
    shares = (fin.get("shares_outstanding") or {}).get("val")
    ttm = fin["trailing_twelve_months"]
    derived = fin["balance_sheet"]["derived"]
    mcap = price * shares if price and shares else None
    ev = mcap - (derived.get("net_cash") or 0) if mcap else None
    return {
        "price": price,
        "market_cap": mcap,
        "enterprise_value": ev,
        "pe_ttm": _ratio(price, ttm.get("eps_diluted")) if (ttm.get("eps_diluted") or 0) > 0 else None,
        "price_to_sales_ttm": _ratio(mcap, ttm.get("revenue")),
        "ev_to_operating_income_ttm": _ratio(ev, ttm.get("operating_income")),
        "free_cash_flow_yield_ttm": _ratio(ttm.get("free_cash_flow"), mcap),
        "price_to_book": _ratio(mcap, (fin["balance_sheet"].get("equity") or {}).get("value")),
    }


def _last_price(ticker: str) -> tuple[float | None, str | None]:
    hist = _yf.history(ticker, "5d", "1d")
    if hist is None or hist.empty:
        return None, None
    return float(hist["Close"].iloc[-1]), hist.index[-1].date().isoformat()


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    cik = await sec.cik_for(ticker)
    if not cik:
        return unavailable(SEGMENT, ticker, "No SEC filer found for this ticker (foreign issuer or ETF?).")

    facts, subs = await sec.company_facts(cik), await sec.submissions(cik)
    fin = build_financials(facts)
    price, price_date = await in_thread(_last_price, ticker)
    latest_filing = next((r for r in sec.recent_filings(subs) if r["form"] in ("10-Q", "10-K")), None)

    data = {
        "company": subs.get("name"),
        "latest_report": {
            "form": latest_filing["form"],
            "period": latest_filing.get("reportDate"),
            "filed": latest_filing["filingDate"],
        }
        if latest_filing
        else None,
        "valuation": {**valuation(fin, price), "price_date": price_date},
        **fin,
    }
    notes = [
        "Quarterly figures are from 10-Q/10-K XBRL; Q4 and cash-flow quarters are derived from year-to-date totals.",
        "Valuation is computed from the latest close and the share count on the latest filing cover page.",
    ]
    status = "ok" if fin["trailing_twelve_months"].get("revenue") and price else "partial"
    return DataPacket(
        segment=SEGMENT,
        ticker=ticker,
        status=status,
        sources=["SEC EDGAR XBRL (10-Q/10-K)", "Yahoo Finance price history"],
        notes=notes,
        data=clean(data),
    )
