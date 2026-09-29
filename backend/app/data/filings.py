"""SEC filings: recent filing activity, latest 10-K/10-Q risk factors & MD&A, recent 8-Ks."""

from __future__ import annotations

from datetime import date, timedelta

from ..schemas import DataPacket
from . import sec
from .base import guarded, unavailable

SEGMENT = "filings"

RISK = [r"item\s*1a\.?\s*risk factors"]
RISK_END = [r"item\s*1b\.?", r"item\s*2\.?\s*(properties|unregistered)"]
MDA = [r"item\s*[27]\.?\s*management'?s discussion and analysis"]
MDA_END = [
    r"item\s*[37]a?\.?\s*quantitative and qualitative",
    r"item\s*8\.?\s*financial statements",
    r"item\s*4\.?\s*controls",
]


@guarded(SEGMENT)
async def fetch(ticker: str) -> DataPacket:
    cik = await sec.cik_for(ticker)
    if not cik:
        return unavailable(SEGMENT, ticker, "No SEC CIK found for this ticker.")
    subs = await sec.submissions(cik)
    recent = subs["filings"]["recent"]
    rows = [dict(zip(recent.keys(), vals, strict=True)) for vals in zip(*recent.values(), strict=True)]
    cutoff = (date.today() - timedelta(days=365)).isoformat()
    last_year = [r for r in rows if r["filingDate"] >= cutoff]

    data: dict = {
        "company": subs.get("name"),
        "filing_counts_last_12m": _counts(last_year),
        "recent_filings": [
            {
                "form": r["form"],
                "date": r["filingDate"],
                "items": r.get("items") or None,
                "description": r.get("primaryDocDescription"),
            }
            for r in last_year[:40]
        ],
    }
    notes: list[str] = []

    periodic = next((r for r in rows if r["form"] in ("10-Q", "10-K")), None)
    if periodic:
        text = await sec.document_text(cik, periodic["accessionNumber"], periodic["primaryDocument"])
        data["latest_periodic"] = {
            "form": periodic["form"],
            "date": periodic["filingDate"],
            "risk_factors_excerpt": sec.section(text, RISK, RISK_END, 12000),
            "mdna_excerpt": sec.section(text, MDA, MDA_END, 15000),
        }

    eight_ks = [r for r in last_year if r["form"] == "8-K"][:3]
    data["recent_8k"] = []
    for r in eight_ks:
        try:
            text = await sec.document_text(cik, r["accessionNumber"], r["primaryDocument"])
            data["recent_8k"].append({"date": r["filingDate"], "items": r.get("items"), "text_excerpt": text[:4000]})
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Could not fetch 8-K from {r['filingDate']}: {exc}")

    return DataPacket(segment=SEGMENT, ticker=ticker, sources=["SEC EDGAR"], notes=notes, data=data)


def _counts(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[r["form"]] = out.get(r["form"], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))
