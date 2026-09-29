"""A few headline numbers (and one small chart series) per data packet, for the website.

These are pulled straight from the packet the analyst read, so the numbers
shown next to an opinion are exactly the numbers behind it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..schemas import DataPacket

Metric = dict[str, Any]


def _m(label: str, value: Any, fmt: str) -> Metric | None:
    return {"label": label, "value": value, "format": fmt} if value is not None else None


def _get(d: Any, *path: Any) -> Any:
    for key in path:
        if isinstance(d, dict):
            d = d.get(key)
        elif isinstance(d, list) and isinstance(key, int) and -len(d) <= key < len(d):
            d = d[key]
        else:
            return None
    return d


def _series(label: str, fmt: str, points: list[tuple[Any, Any]]) -> dict | None:
    pts = [{"t": t, "v": v} for t, v in points if t is not None and v is not None]
    return {"label": label, "format": fmt, "points": pts} if len(pts) >= 2 else None


def _price(d: dict) -> tuple[list, dict | None]:
    return [
        _m("Last close", d.get("last_close"), "usd"),
        _m("1-month", _get(d, "returns", "1m"), "pct"),
        _m("1-year", _get(d, "returns", "1y"), "pct"),
        _m("RSI (14)", _get(d, "momentum", "rsi14"), "num"),
        _m("vs 200-day avg", _get(d, "moving_averages", "price_vs_sma200"), "pct"),
    ], _series(
        "Weekly close, last 12 months",
        "usd",
        [(w.get("week"), w.get("close")) for w in d.get("weekly_closes_last_52") or []],
    )


def _financials(d: dict) -> tuple[list, dict | None]:
    q = d.get("quarterly_last_8") or {}
    return [
        _m("Revenue (TTM)", _get(d, "trailing_twelve_months", "revenue"), "usd_big"),
        _m("Revenue growth (TTM)", _get(d, "trailing_twelve_months", "revenue_growth_vs_prior_ttm"), "pct"),
        _m("Operating margin (TTM)", _get(d, "trailing_twelve_months", "operating_margin"), "pct"),
        _m("P/E (TTM)", _get(d, "valuation", "pe_ttm"), "num"),
        _m("FCF yield", _get(d, "valuation", "free_cash_flow_yield_ttm"), "pct"),
        _m("Net cash", _get(d, "balance_sheet", "derived", "net_cash"), "usd_big"),
    ], _series(
        "Quarterly revenue", "usd_big", list(zip(q.get("period_ends") or [], q.get("revenue") or [], strict=False))
    )


def _analysts(d: dict) -> tuple[list, dict | None]:
    latest = _get(d, "recommendation_trend_by_month", 0) or {}
    buys = (latest.get("strongBuy") or 0) + (latest.get("buy") or 0)
    sells = (latest.get("strongSell") or 0) + (latest.get("sell") or 0)
    return [
        _m("Buy ratings", buys if latest else None, "int"),
        _m("Hold ratings", latest.get("hold"), "int"),
        _m("Sell ratings", sells if latest else None, "int"),
        _m("Mean target", _get(d, "price_targets", "mean"), "usd"),
    ], None


def _earnings(d: dict) -> tuple[list, dict | None]:
    eps = _get(d, "reported_results_sec", "eps_diluted") or []
    last = eps[-1] if eps else {}
    return [
        _m("Latest EPS", last.get("value"), "usd"),
        _m("EPS growth (YoY)", last.get("yoy_growth"), "pct"),
        _m("Quarter ended", last.get("quarter_end"), "date"),
        _m("Next report", _get(d, "upcoming_report", "date"), "date"),
    ], _series("Quarterly diluted EPS", "usd", [(e.get("quarter_end"), e.get("value")) for e in eps])


def _insiders(d: dict) -> tuple[list, dict | None]:
    return [
        _m("Buys (90d)", _get(d, "summary_90d", "open_market_buys"), "int"),
        _m("Sells (90d)", _get(d, "summary_90d", "open_market_sells"), "int"),
        _m("Sold (12m)", _get(d, "summary_12m", "sell_value_usd"), "usd_big"),
        _m("Bought (12m)", _get(d, "summary_12m", "buy_value_usd"), "usd_big"),
    ], None


def _congress(d: dict) -> tuple[list, dict | None]:
    return [
        _m("Trades (12m)", d.get("trades_last_12m"), "int"),
        _m("Purchases", d.get("purchases"), "int"),
        _m("Sales", d.get("sales"), "int"),
    ], None


def _news(d: dict) -> tuple[list, dict | None]:
    articles = d.get("articles") or []
    return [
        _m("Articles (21d)", len(articles) if articles else None, "int"),
        _m("Latest", _get(articles, 0, "date"), "date"),
    ], None


def _filings(d: dict) -> tuple[list, dict | None]:
    counts = d.get("filing_counts_last_12m") or {}
    return [
        _m("Filings (12m)", sum(counts.values()) if counts else None, "int"),
        _m("8-Ks (12m)", counts.get("8-K"), "int"),
        _m("Latest report", _get(d, "latest_periodic", "form"), "text"),
        _m("Filed", _get(d, "latest_periodic", "date"), "date"),
    ], None


def _institutions(d: dict) -> tuple[list, dict | None]:
    return [
        _m("Short % of float", d.get("short_pct_of_float"), "pct"),
        _m("Days to cover", d.get("short_ratio_days_to_cover"), "num"),
        _m("Top holder", _get(d, "top_institutions", 0, "Holder"), "text"),
    ], None


def _options(d: dict) -> tuple[list, dict | None]:
    near = _get(d, "expirations", 0) or {}
    return [
        _m("Put/call (volume)", near.get("put_call_volume_ratio"), "num"),
        _m("ATM implied vol", near.get("atm_iv"), "pct"),
        _m("Implied move", near.get("implied_move_pct"), "pct"),
        _m("Max pain", near.get("max_pain"), "usd"),
        _m("Expiry", near.get("expiration"), "date"),
    ], None


def _economy(d: dict) -> tuple[list, dict | None]:
    ind = d.get("indicators") or {}
    return [
        _m("Fed funds", _get(ind, "FEDFUNDS", "latest", "value"), "rate"),
        _m("10Y yield", _get(ind, "DGS10", "latest", "value"), "rate"),
        _m("CPI (YoY)", _get(ind, "CPIAUCSL", "yoy_pct"), "rate"),
        _m("Unemployment", _get(ind, "UNRATE", "latest", "value"), "rate"),
    ], None


def _related(d: dict) -> tuple[list, dict | None]:
    spy = next((m for m in d.get("macro_markets") or [] if m.get("symbol") == "SPY"), {})
    stock_3m = _get(d, "stock", "performance", "3m")
    spy_3m = _get(spy, "performance", "3m")
    return [
        _m("3-month return", stock_3m, "pct"),
        _m("vs S&P 500 (3m)", stock_3m - spy_3m if stock_3m is not None and spy_3m is not None else None, "pct"),
        _m("Beta vs S&P 500", spy.get("beta"), "num"),
        _m("Sector ETF (3m)", _get(d, "sector_etf", "performance", "3m"), "pct"),
    ], None


BUILDERS: dict[str, Callable[[dict], tuple[list, dict | None]]] = {
    "price": _price,
    "financials": _financials,
    "analysts": _analysts,
    "earnings": _earnings,
    "insiders": _insiders,
    "congress": _congress,
    "news": _news,
    "filings": _filings,
    "institutions": _institutions,
    "options": _options,
    "economy": _economy,
    "related": _related,
}


def highlights(packet: DataPacket) -> dict[str, Any]:
    builder = BUILDERS.get(packet.segment)
    if builder is None or packet.status == "unavailable":
        return {"metrics": [], "series": None}
    try:
        metrics, series = builder(packet.data)
    except Exception:  # noqa: BLE001 - highlights are decoration; never break a run over them
        return {"metrics": [], "series": None}
    return {"metrics": [m for m in metrics if m is not None], "series": series}
