"""Company-list loading: one download at a time, backoff after failure, Nasdaq backup list."""

import asyncio

import pytest

from app import search

HEADER = (
    "Nasdaq Traded|Symbol|Security Name|Listing Exchange|Market Category|ETF|Round Lot Size|Test Issue"
    "|Financial Status|CQS Symbol|NASDAQ Symbol|NextShares"
)
NASDAQ = (
    HEADER
    + """
Y|AAPL|Apple Inc. - Common Stock|Q|Q|N|100|N|N||AAPL|N
Y|SPY|SPDR S&P 500 ETF Trust|P| |Y|100|N||SPY|SPY|N
Y|ZZZT|Test Issue Corp - Common Stock|Q|Q|N|100|Y|N||ZZZT|N
Y|KO|Coca-Cola Company (The) Common Stock|N| |N|100|N||KO|KO|N
File Creation Time: 0930202612:00||||||||||"""
)


@pytest.fixture
def fresh(monkeypatch):
    monkeypatch.setattr(search, "_index", [])
    monkeypatch.setattr(search, "_loaded_at", 0.0)
    monkeypatch.setattr(search, "_failed_at", 0.0)
    monkeypatch.setattr(search, "_lock", asyncio.Lock())
    # conftest stubs ensure_index for other tests; use the real one here.
    monkeypatch.setattr(search, "ensure_index", ENSURE)


ENSURE = search.ensure_index


def test_parse_nasdaq_keeps_stocks_only():
    rows = search.parse_nasdaq(NASDAQ)
    assert [(r["ticker"], r["name"], r["exchange"]) for r in rows] == [
        ("AAPL", "Apple Inc.", "Nasdaq"),
        ("KO", "Coca-Cola Company (The) Common Stock", "NYSE"),
    ]


def test_falls_back_to_nasdaq_when_sec_blocks(fresh, monkeypatch):
    async def blocked(*a, **k):
        raise RuntimeError("403 Forbidden")

    async def nasdaq(url, headers=None):
        return NASDAQ

    monkeypatch.setattr(search, "get_json", blocked)
    monkeypatch.setattr(search, "get_text", nasdaq)
    assert [r["ticker"] for r in asyncio.run(search.search("apple"))] == ["AAPL"]


def test_one_download_for_many_searches_and_backoff_after_failure(fresh, monkeypatch):
    calls = []

    async def failing(*a, **k):
        calls.append(1)
        await asyncio.sleep(0.01)
        raise RuntimeError("down")

    monkeypatch.setattr(search, "get_json", failing)
    monkeypatch.setattr(search, "get_text", failing)

    async def burst():
        return await asyncio.gather(*(search.search("aapl") for _ in range(10)))

    assert asyncio.run(burst()) == [[]] * 10
    assert len(calls) == 3  # SEC x2 + Nasdaq, once, not once per keystroke
    asyncio.run(search.search("aapl"))
    assert len(calls) == 3  # still backing off


def test_api_says_unavailable_when_no_list_loaded():
    from fastapi.testclient import TestClient

    from app import main

    with TestClient(main.app) as client:  # conftest: the list never loads in tests
        resp = client.get("/api/search?q=aapl")
    assert resp.status_code == 503
