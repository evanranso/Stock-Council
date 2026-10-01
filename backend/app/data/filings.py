"""SEC filings: recent filing activity, latest 10-K/10-Q risk factors & MD&A, recent 8-Ks."""

from __future__ import annotations

import re
from datetime import date, timedelta

from ..schemas import DataPacket
from . import sec
from .base import guarded, unavailable

SEGMENT = "filings"

RISK = [r"item\s*1a\.?\s*risk factors"]
RISK_END = [r"item\s*1b\.?", r"item\s*2\.?\s*(properties|unregistered)"]
MDA = [r"item\s*[27]\.?\s*management'?s discussion and analysis"]
# Forms that carry no news for this analyst: insider forms (the Insider analyst reads them), ownership
# filings (Institutional analyst), and routine registration/offering paperwork.
ROUTINE_FORMS = {
    "3",
    "4",
    "5",
    "3/A",
    "4/A",
    "5/A",
    "144",
    "SC 13G",
    "SC 13G/A",
    "SCHEDULE 13G",
    "SCHEDULE 13G/A",
    "S-8",
    "S-8 POS",
    "FWP",
    "424B2",
    "424B3",
    "424B5",
    "CERT",
    "CERTNYS",
    "CERTNAS",
    "IRANNOTICE",
}
# What each 8-K item number means, so the analyst doesn't need the filing's cover page to know.
EIGHT_K_ITEMS = {
    "1.01": "material agreement",
    "1.02": "agreement terminated",
    "1.03": "bankruptcy",
    "1.05": "cybersecurity incident",
    "2.01": "acquisition/disposition completed",
    "2.02": "results of operations",
    "2.03": "new debt obligation",
    "2.04": "debt acceleration",
    "2.05": "restructuring/exit costs",
    "2.06": "material impairment",
    "3.01": "delisting notice",
    "3.02": "unregistered equity sale",
    "3.03": "change to shareholder rights",
    "4.01": "auditor change",
    "4.02": "prior financials no longer reliable",
    "5.01": "change in control",
    "5.02": "executive/director change",
    "5.03": "charter/bylaw amendment",
    "5.07": "shareholder vote results",
    "7.01": "Reg FD disclosure",
    "8.01": "other events",
    "9.01": "exhibits",
}
BOILERPLATE = re.compile(
    r"[^.]*(forward-looking statements?|should be read in conjunction with|safe harbor)[^.]*\.", re.IGNORECASE
)
EIGHT_K_START = re.compile(r"\bItem\s+\d\.\d{2}\b", re.IGNORECASE)
EIGHT_K_END = re.compile(r"\bSIGNATURES?\b")


def _excerpt(text: str | None, limit: int) -> str | None:
    """Drop forward-looking-statement boilerplate, then cap the length."""
    if not text:
        return None
    return re.sub(r"\s+", " ", BOILERPLATE.sub(" ", text)).strip()[:limit]


def eight_k_body(text: str, limit: int = 1500) -> str:
    """An 8-K's substance: from the first 'Item x.xx' to the signature block, skipping the cover page."""
    start = EIGHT_K_START.search(text)
    body = text[start.start() :] if start else text
    end = EIGHT_K_END.search(body)
    return re.sub(r"\s+", " ", body[: end.start()] if end else body).strip()[:limit]


def item_labels(items: str | None) -> list[str]:
    codes = [c.strip() for c in (items or "").split(",") if c.strip()]
    return [f"{c} {EIGHT_K_ITEMS.get(c, '')}".strip() for c in codes if c != "9.01"]


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
        "material_filings": [
            {
                "form": r["form"],
                "date": r["filingDate"],
                **({"items": item_labels(r.get("items"))} if r.get("items") else {}),
            }
            for r in last_year
            if r["form"] not in ROUTINE_FORMS
        ][:15],
    }
    notes: list[str] = []

    periodic = next((r for r in rows if r["form"] in ("10-Q", "10-K")), None)
    if periodic:
        text = await sec.document_text(cik, periodic["accessionNumber"], periodic["primaryDocument"])
        data["latest_periodic"] = {
            "form": periodic["form"],
            "date": periodic["filingDate"],
            "risk_factors_excerpt": _excerpt(sec.section(text, RISK, RISK_END, 9000), 5000),
            "mdna_excerpt": _excerpt(sec.section(text, MDA, MDA_END, 14000), 8000),
        }

    eight_ks = [r for r in last_year if r["form"] == "8-K"][:4]
    data["recent_8k"] = []
    for r in eight_ks:
        try:
            text = await sec.document_text(cik, r["accessionNumber"], r["primaryDocument"])
            data["recent_8k"].append(
                {"date": r["filingDate"], "items": item_labels(r.get("items")), "text_excerpt": eight_k_body(text)}
            )
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Could not fetch 8-K from {r['filingDate']}: {exc}")

    return DataPacket(segment=SEGMENT, ticker=ticker, sources=["SEC EDGAR"], notes=notes, data=data)


def _counts(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[r["form"]] = out.get(r["form"], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))
