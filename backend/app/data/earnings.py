"""Earnings: expectations (estimates, surprises, next report) plus the trend of reported results.

Reported quarterly EPS and revenue always come from SEC filings. Consensus
estimates and beat/miss history need Finnhub (free key) or Yahoo (often
blocked from cloud servers).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..schemas import DataPacket
from . import _yf, sec, xbrl
from .base import clean, df_records, finnhub, guarded, in_thread, unavailable
from .financials import FLOWS

SEGMENT = "earnings"


def reported_trend(facts: dict) -> dict:
    out: dict = {}
    for key in ("eps_diluted", "revenue"):
        _, rows = xbrl.concept_rows(facts, FLOWS[key])
        quarters = xbrl.quarterly(rows)
        out[key] = [
            {
                "quarter_end": q["end"],
                "value": q["val"],
                "yoy_growth": xbrl.growth(q["val"], xbrl.value_near(quarters, xbrl.year_ago(q["end"]))),
                "derived_from_annual": q["derived"],
            }
            for q in quarters[-8:]
        ]
    return out


def _yahoo(ticker: str) -> dict:
    fields = ["earnings_estimate", "revenue_estimate", "eps_trend", "eps_revisions", "earnings_history"]
    return {f: df_records(_yf.safe_attr(ticker, f)) for f in fields}


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    data: dict = {}
    sources: list[str] = []
    notes: list[str] = []

    cik = await sec.cik_for(ticker)
    if cik:
        data["reported_results_sec"] = reported_trend(await sec.company_facts(cik))
        subs = await sec.submissions(cik)
        last = next((r for r in sec.recent_filings(subs) if r["form"] in ("10-Q", "10-K")), None)
        if last and last.get("reportDate"):
            period_end = datetime.fromisoformat(last["reportDate"])
            data["last_report"] = {"form": last["form"], "period_end": last["reportDate"], "filed": last["filingDate"]}
            data["next_quarter_end_estimate"] = (period_end + timedelta(days=91)).date().isoformat()
        sources.append("SEC EDGAR XBRL (reported results)")

    try:
        today = datetime.now(UTC).date()
        data["surprises_last_4q"] = await finnhub("stock/earnings", symbol=ticker)
        cal = await finnhub(
            "calendar/earnings",
            symbol=ticker,
            **{"from": today.isoformat(), "to": (today + timedelta(days=120)).isoformat()},
        )
        data["upcoming_report"] = (cal.get("earningsCalendar") or [None])[0]
        sources.append("Finnhub (estimates, surprises, calendar)")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"No consensus estimates or beat/miss history: add FINNHUB_API_KEY ({exc}).")

    yahoo = await in_thread(_yahoo, ticker)
    if any(yahoo.values()):
        data["yahoo_estimates"] = yahoo
        sources.append("Yahoo Finance estimates")

    if not data:
        return unavailable(SEGMENT, ticker, "No earnings data found. " + " ".join(notes))
    has_expectations = bool(data.get("surprises_last_4q") or data.get("upcoming_report") or data.get("yahoo_estimates"))
    return DataPacket(
        segment=SEGMENT,
        ticker=ticker,
        status="ok" if has_expectations else "partial",
        sources=sources,
        notes=notes,
        data=clean(data),
    )
