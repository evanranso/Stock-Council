"""Turn SEC XBRL company facts into clean quarterly, annual, and trailing-twelve-month series.

Two things make raw XBRL tricky:
  * Companies change tags over time (Apple used "Revenues" years ago and
    "RevenueFromContractWithCustomerExcludingAssessedTax" now), so we pick the
    candidate tag with the most recent data, not the first one that exists.
  * 10-Qs often report year-to-date totals (6 and 9 months), especially for
    cash flow, and Q4 is never filed on its own. Quarters are derived by
    differencing consecutive year-to-date values.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

UNIT_PREFERENCE = ("USD", "USD/shares", "shares", "pure")


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _days(row: dict) -> int | None:
    if not row.get("start"):
        return None
    return (_d(row["end"]) - _d(row["start"])).days


def concept_rows(facts: dict, concepts: list[str], taxonomy: str = "us-gaap") -> tuple[str | None, list[dict]]:
    """Rows for whichever candidate concept has the newest data."""
    best: tuple[str | None, list[dict], str] = (None, [], "")
    tax = facts.get("facts", {}).get(taxonomy, {})
    for name in concepts:
        units = tax.get(name, {}).get("units", {})
        rows = next((units[u] for u in UNIT_PREFERENCE if u in units), None)
        if rows is None and units:
            rows = next(iter(units.values()))
        if not rows:
            continue
        latest = max(r["end"] for r in rows)
        if latest > best[2]:
            best = (name, rows, latest)
    return best[0], best[1]


def _dedupe(rows: list[dict]) -> list[dict]:
    """One value per (start, end) period: the most recently filed (restatements win)."""
    out: dict[tuple, dict] = {}
    for r in rows:
        key = (r.get("start"), r["end"])
        if key not in out or r.get("filed", "") > out[key].get("filed", ""):
            out[key] = r
    return list(out.values())


def quarterly(rows: list[dict]) -> list[dict]:
    """Quarter values ([{start, end, val, derived}]) oldest first, including derived Q4s."""
    rows = [r for r in _dedupe(rows) if r.get("start")]
    quarters: dict[str, dict] = {}
    for r in rows:
        if 80 <= (_days(r) or 0) <= 100:
            quarters[r["end"]] = {"start": r["start"], "end": r["end"], "val": r["val"], "derived": False}

    # Year-to-date chains share a start date: Q1 (3m), H1 (6m), 9m, FY (12m).
    by_start: dict[str, list[dict]] = {}
    for r in rows:
        by_start.setdefault(r["start"], []).append(r)
    for chain in by_start.values():
        chain.sort(key=lambda r: r["end"])
        for prev, cur in zip(chain, chain[1:], strict=False):
            gap = (_d(cur["end"]) - _d(prev["end"])).days
            if 80 <= gap <= 100 and cur["end"] not in quarters:
                start = (_d(prev["end"]) + timedelta(days=1)).isoformat()
                quarters[cur["end"]] = {
                    "start": start,
                    "end": cur["end"],
                    "val": cur["val"] - prev["val"],
                    "derived": True,
                }

    # Fiscal Q4 when only the three quarters and the full year were filed: FY minus Q1-Q3.
    for r in rows:
        if not 350 <= (_days(r) or 0) <= 380 or r["end"] in quarters:
            continue
        inside = [q for q in quarters.values() if q["start"] >= r["start"] and q["end"] < r["end"]]
        if len(inside) == 3:
            last = max(q["end"] for q in inside)
            quarters[r["end"]] = {
                "start": (_d(last) + timedelta(days=1)).isoformat(),
                "end": r["end"],
                "val": r["val"] - sum(q["val"] for q in inside),
                "derived": True,
            }
    return sorted(quarters.values(), key=lambda q: q["end"])


def annual(rows: list[dict]) -> list[dict]:
    """Fiscal-year values ([{start, end, val}]) oldest first."""
    years = [
        {"start": r["start"], "end": r["end"], "val": r["val"]}
        for r in _dedupe(rows)
        if r.get("start") and 350 <= (_days(r) or 0) <= 380
    ]
    return sorted(years, key=lambda y: y["end"])


def ttm(quarters: list[dict]) -> dict | None:
    """Sum of the latest four consecutive quarters."""
    if len(quarters) < 4:
        return None
    last4 = quarters[-4:]
    for a, b in zip(last4, last4[1:], strict=False):
        if not 80 <= (_d(b["end"]) - _d(a["end"])).days <= 100:
            return None
    return {"start": last4[0]["start"], "end": last4[-1]["end"], "val": sum(q["val"] for q in last4)}


def instants(rows: list[dict]) -> list[dict]:
    """Point-in-time values (balance sheet, share counts), oldest first."""
    points = {}
    for r in rows:
        if r.get("start"):
            continue
        if r["end"] not in points or r.get("filed", "") > points[r["end"]].get("filed", ""):
            points[r["end"]] = r
    return [{"end": e, "val": points[e]["val"]} for e in sorted(points)]


def value_near(series: list[dict], target_end: str, tolerance_days: int = 20) -> Any:
    """Value whose period ends within tolerance of target_end (e.g. the same quarter a year ago)."""
    t = _d(target_end)
    for row in series:
        if abs((_d(row["end"]) - t).days) <= tolerance_days:
            return row["val"]
    return None


def year_ago(end: str) -> str:
    d = _d(end)
    return (d - timedelta(days=364)).isoformat()


def growth(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev in (None, 0):
        return None
    return cur / abs(prev) - 1 if prev > 0 else None
