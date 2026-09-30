"""Search ranking, website highlights, and server-side runs that survive a closed tab."""

import asyncio

from app import main, search
from app.data.highlights import highlights
from app.schemas import DataPacket

ROWS = [  # SEC order is roughly by size
    {"ticker": "AAPL", "name": "Apple Inc.", "exchange": "Nasdaq"},
    {"ticker": "MSFT", "name": "MICROSOFT CORP", "exchange": "Nasdaq"},
    {"ticker": "APLE", "name": "Apple Hospitality REIT, Inc.", "exchange": "NYSE"},
    {"ticker": "PINE", "name": "Pineapple Energy Inc.", "exchange": "OTC"},
    {"ticker": "AAPL", "name": "Apple Inc. duplicate", "exchange": "Nasdaq"},
]
INDEX = search.build_index(ROWS)


def tickers(q):
    return [r["ticker"] for r in search.rank_matches(INDEX, q)]


def test_company_name_finds_the_ticker_biggest_first():
    assert tickers("apple") == ["AAPL", "APLE"]
    assert tickers("Apple Inc") == ["AAPL", "APLE"]


def test_ticker_prefix_and_exact_ticker():
    assert tickers("msft") == ["MSFT"]
    assert tickers("AA") == ["AAPL"]


def test_word_boundary_matching_skips_mid_word_hits():
    assert "PINE" not in tickers("apple")  # "pineapple" shouldn't match "apple"
    assert tickers("hospitality") == ["APLE"]


def test_duplicates_dropped_and_internal_fields_hidden():
    rows = search.rank_matches(INDEX, "AAPL")
    assert len(rows) == 1 and set(rows[0]) == {"ticker", "name", "exchange"}


def test_highlights_for_price_and_unavailable():
    packet = DataPacket(
        segment="price",
        ticker="X",
        data={
            "last_close": 10.0,
            "returns": {"1m": 0.05},
            "weekly_closes_last_52": [{"week": "2026-01-04", "close": 9}, {"week": "2026-01-11", "close": 10}],
        },
    )
    h = highlights(packet)
    assert {m["label"] for m in h["metrics"]} == {"Last close", "1-month"}
    assert h["series"]["points"] == [{"t": "2026-01-04", "v": 9}, {"t": "2026-01-11", "v": 10}]
    empty = DataPacket(segment="price", ticker="X", status="unavailable")
    assert highlights(empty) == {"metrics": [], "series": None}


async def test_live_run_can_be_rejoined_after_the_viewer_leaves(monkeypatch):
    gate = asyncio.Event()

    async def fake_council(symbol, depth=None):
        yield {"type": "start"}
        await gate.wait()
        yield {"type": "done", "run": {"ticker": symbol}}

    monkeypatch.setattr(main, "run_council", fake_council)
    monkeypatch.setattr(main.cache, "save_run", lambda *a: None)
    monkeypatch.setattr(main.cache, "record_verdict", lambda *a: None)

    run = main.LiveRun("ZZZ")
    task = asyncio.create_task(run.drive())
    first = run.follow()
    assert (await anext(first))["type"] == "start"
    await first.aclose()  # the first viewer closes the tab mid-run

    gate.set()
    await task
    replay = [e["type"] async for e in run.follow()]  # a returning viewer gets the whole run
    assert replay == ["start", "done"]
