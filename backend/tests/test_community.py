"""The community library: every completed analysis, filterable by time, rating, timeframe and depth."""

import json
import time

from fastapi.testclient import TestClient

from app import auth, cache, main


def events(ticker, weeks, months, years, depth="standard", finished="2026-09-30T12:00:00Z"):
    horizon = lambda s, c: {"score": s, "confidence": c, "rationale": "r"}  # noqa: E731
    return [
        {"type": "start", "ticker": ticker, "company_name": f"{ticker} Inc", "depth": depth},
        {
            "type": "verdict",
            "verdict": {
                "rating": "hold",
                "score": 0,
                "confidence": 50,
                "bottom_line": f"{ticker} bottom line",
                "weeks": horizon(weeks, 40),
                "months": horizon(months, 60),
                "years": horizon(years, 70),
            },
        },
        {"type": "done", "run": {"ticker": ticker, "finished_at": finished, "depth": depth}},
    ]


def setup_library():
    cache.save_analysis("VRA", events("VRA", 4.7, 22.7, 6.4), 9.5)
    cache.save_analysis("FSLR", events("FSLR", -11.7, 2.9, 10.6, depth="deep"))
    cache.save_analysis("META", events("META", 4.4, -6.7, 7.0, depth="quick"))
    cache.save_analysis("VRA", events("VRA", 4.7, 22.7, 6.4), 9.5)  # same run delivered twice: stored once


def get(client, **params):
    return client.get("/api/community", params=params).json()


def test_filters_and_sorting():
    setup_library()
    with TestClient(main.app) as client:
        everything = get(client, days="all")
        assert everything["total"] == 3 and everything["items"][0]["ticker"] == "META"  # newest first
        buys = get(client, days="all", rating="buy", horizon="months")
        assert [i["ticker"] for i in buys["items"]] == ["VRA"] and buys["items"][0]["rating"] == "buy"
        assert [i["ticker"] for i in get(client, days="all", rating="sell", horizon="weeks")["items"]] == ["FSLR"]
        assert [i["ticker"] for i in get(client, days="all", depth="deep")["items"]] == ["FSLR"]
        years = get(client, days="all", horizon="years", sort="bullish")
        assert [i["ticker"] for i in years["items"]] == ["FSLR", "META", "VRA"]
        assert get(client, days="all", horizon="years", sort="confidence")["items"][0]["confidence"] == 70
        assert [i["ticker"] for i in get(client, days="all", q="meta")["items"]] == ["META"]


def test_open_an_analysis_needs_an_account_and_time_window():
    setup_library()
    with TestClient(main.app) as client:
        item = get(client, days="all", q="VRA")["items"][0]  # the list itself is public
        assert client.get(f"/api/community/{item['id']}").status_code == 401  # reading a report is not
        main.app.dependency_overrides[auth.require_user] = lambda: auth.User("u1", "a@example.com")
        try:
            full = client.get(f"/api/community/{item['id']}").json()
            assert full["ticker"] == "VRA" and full["events"][-1]["type"] == "done"
            assert client.get("/api/community/nope").status_code == 404
        finally:
            main.app.dependency_overrides.clear()
    with cache._db() as conn:
        conn.execute("UPDATE analyses SET created = ? WHERE ticker = 'META'", (time.time() - 10 * 86400,))
    with TestClient(main.app) as client:
        assert {i["ticker"] for i in get(client, days="7")["items"]} == {"VRA", "FSLR"}


def test_seeded_from_existing_runs():
    cache.save_run("DG", events("DG", 3.5, 18.3, 14.7), "standard")
    cache._ready.clear()
    with cache._db() as conn:  # a database from before the library existed
        conn.execute("DELETE FROM analyses")
    cache._ready.clear()
    rows = cache.list_analyses()
    assert [r["ticker"] for r in rows] == ["DG"] and json.dumps(rows)
