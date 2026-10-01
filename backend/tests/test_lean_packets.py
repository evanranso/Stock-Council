"""What the analysts read: noise trimmed, signal kept."""

from datetime import date, timedelta

from app.agents.specialists import analyst_view
from app.data import economy, filings, news
from app.data.base import clean
from app.schemas import DataPacket


def test_numbers_rounded_to_significant_digits():
    assert clean({"rev": 124_312_345_678.0, "margin": 0.318237498, "price": 249.15, "n": 3.0}) == {
        "rev": 124_310_000_000,
        "margin": 0.31824,
        "price": 249.15,
        "n": 3,
    }


def test_chart_only_fields_are_hidden_from_the_analyst():
    p = DataPacket(segment="price", ticker="X", data={"last_close": 10.123456, "weekly_closes_last_52": [1, 2]})
    assert analyst_view(p) == {"last_close": 10.123}


def test_8k_skips_cover_page_and_signatures():
    text = "SECURITIES AND EXCHANGE COMMISSION FORM 8-K Check the appropriate box " * 30 + (
        "Item 5.02 Departure of Directors. The CFO resigned. SIGNATURE Pursuant to the requirements"
    )
    assert filings.eight_k_body(text) == "Item 5.02 Departure of Directors. The CFO resigned."
    assert filings.item_labels("2.02,9.01") == ["2.02 results of operations"]


def test_boilerplate_removed_from_excerpts():
    text = "This report contains forward-looking statements. Revenue grew 12%. Read it in conjunction. Margins rose."
    assert filings._excerpt(text, 500) == "Revenue grew 12%. Read it in conjunction. Margins rose."


def test_news_dedupes_and_prefers_company_stories():
    arts = [
        {"date": "2026-09-30", "headline": "5 stocks to watch", "summary": "Tesla and more"},
        {"date": "2026-09-29", "headline": "Amazon launches chip", "summary": "AWS customers get Trainium 3."},
        {"date": "2026-09-29", "headline": "Amazon launches chip!", "summary": "Same story elsewhere."},
        {"date": "2026-09-28", "headline": "AMZN upgraded", "summary": "AMZN upgraded"},
    ]
    picked = news.curate(arts, "AMZN", "AMAZON COM INC", limit=2)
    assert [a["headline"] for a in picked] == ["Amazon launches chip", "AMZN upgraded"]
    assert "summary" not in picked[1]  # summary only repeated the headline


def test_economy_reports_trend_not_every_point():
    obs = [{"date": (date(2026, 9, 30) - timedelta(days=i)).isoformat(), "value": 4 + i / 1000} for i in range(400)]
    entry = economy.summarize_series("DGS10", "10Y", obs)
    assert entry["latest"]["value"] == 4 and set(entry) == {"label", "latest", "3m_ago", "1y_ago"}
    days = [date(2026, 9, 1), date(2026, 9, 1) - timedelta(days=365)]
    cpi = [{"date": d.isoformat(), "value": v} for d, v in zip(days, [103, 100], strict=True)]
    assert economy.summarize_series("CPIAUCSL", "CPI", cpi)["yoy_pct"] == 3.0


def test_scope_describes_what_was_pulled():
    from app.data.highlights import scope

    fin = DataPacket(
        segment="financials",
        ticker="X",
        data={
            "quarterly_last_8": {"period_ends": ["q"] * 8},
            "annual_last_5": {"fiscal_year_ends": ["y"] * 5},
            "latest_report": {"form": "10-Q", "filed": "2026-07-31"},
        },
    )
    assert scope(fin) == ["8 quarters + 5 fiscal years of statements", "latest 10-Q filed 2026-07-31"]
    ins = DataPacket(segment="insiders", ticker="X", data={"form4_filings_read": 60, "open_market_trades": []})
    assert scope(ins) == ["60 Form 4 filings (12 months)", "0 open-market trades"]  # zero is a real finding
    news_p = DataPacket(segment="news", ticker="X", data={"articles": [{}] * 20, "articles_found_21d": 40})
    assert scope(news_p) == ["40 articles from the last 3 weeks", "20 most relevant kept"]
    assert scope(DataPacket(segment="news", ticker="X", status="unavailable")) == []
