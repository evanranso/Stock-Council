"""Parsers for the free data sources, tested against sample payloads in each source's real format."""

from datetime import UTC, date, datetime

import pytest

from app.data import economy, financials, insiders, news, options, sec, xbrl


def flow(start, end, val, filed="2026-01-01", form="10-Q"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form}


# Apple-like fiscal year ending late September. The 10-Qs report Q1 as 3 months and
# cash flow only as year-to-date; Q4 is never filed on its own.
REVENUE = [
    flow("2024-09-29", "2024-12-28", 124.3),
    flow("2024-12-29", "2025-03-29", 95.4),
    flow("2025-03-30", "2025-06-28", 94.0),
    flow("2024-09-29", "2025-09-27", 416.0, form="10-K"),
    flow("2025-09-28", "2025-12-27", 140.0),
    flow("2025-12-28", "2026-03-28", 105.0),
    flow("2026-03-29", "2026-06-27", 103.0),
]
OCF_YTD = [
    flow("2025-09-28", "2025-12-27", 30.0),
    flow("2025-09-28", "2026-03-28", 55.0),
    flow("2025-09-28", "2026-06-27", 83.0),
]
FACTS = {
    "facts": {
        "us-gaap": {
            # Old tag with stale data must lose to the current tag.
            "Revenues": {"units": {"USD": [flow("2016-09-25", "2017-09-30", 229.0, form="10-K")]}},
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": REVENUE}},
            "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": OCF_YTD}},
            "EarningsPerShareDiluted": {"units": {"USD/shares": [flow("2025-09-28", "2025-12-27", 2.4)]}},
            "CashAndCashEquivalentsAtCarryingValue": {
                "units": {"USD": [{"end": "2025-06-28", "val": 25.0}, {"end": "2026-06-27", "val": 30.0}]}
            },
            "LongTermDebtNoncurrent": {"units": {"USD": [{"end": "2026-06-27", "val": 80.0}]}},
        },
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [{"end": "2026-07-20", "val": 10.0}]}}},
    }
}


def test_newest_tag_wins_over_first_listed_tag():
    tag, _ = xbrl.concept_rows(FACTS, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"])
    assert tag == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_q4_is_derived_from_the_annual_total():
    _, rows = xbrl.concept_rows(FACTS, financials.FLOWS["revenue"])
    q = {r["end"]: r for r in xbrl.quarterly(rows)}
    assert q["2025-09-27"]["val"] == pytest.approx(416.0 - 124.3 - 95.4 - 94.0)
    assert q["2025-09-27"]["derived"] is True


def test_ytd_cash_flow_becomes_quarters():
    _, rows = xbrl.concept_rows(FACTS, financials.FLOWS["operating_cash_flow"])
    assert [round(q["val"], 1) for q in xbrl.quarterly(rows)] == [30.0, 25.0, 28.0]


def test_ttm_uses_the_latest_four_quarters():
    _, rows = xbrl.concept_rows(FACTS, financials.FLOWS["revenue"])
    t = xbrl.ttm(xbrl.quarterly(rows))
    assert t["end"] == "2026-06-27"
    assert t["val"] == pytest.approx((416.0 - 124.3 - 95.4 - 94.0) + 140 + 105 + 103)


def test_build_financials_is_current_and_computes_valuation():
    fin = financials.build_financials(FACTS)
    assert fin["latest_quarter_end"] == "2026-06-27"
    assert fin["quarterly_last_8"]["revenue_growth_yoy"][-1] == pytest.approx(103 / 94 - 1)
    bs = fin["balance_sheet"]
    assert bs["cash"]["value"] == 30.0 and bs["cash"]["year_ago"] == 25.0
    val = financials.valuation(fin, price=50.0)
    assert val["market_cap"] == 500.0
    assert val["enterprise_value"] == pytest.approx(500 + 80 - 30)


FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
  <aff10b5One>1</aff10b5One>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>CFO</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-09-01</value></transactionDate>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>200.5</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>5000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


def test_form4_parsing_and_summary():
    rows = insiders.parse_form4(FORM4)
    assert rows == [
        {
            "name": "Doe Jane",
            "role": "CFO",
            "date": "2026-09-01",
            "code": "S",
            "shares": -1000.0,
            "price": 200.5,
            "shares_owned_after": 5000.0,
            "planned_10b5_1": True,
        }
    ]
    s = insiders.summarize(rows, 90, today=datetime(2026, 9, 29, tzinfo=UTC))
    assert s["open_market_sells"] == 1 and s["sell_value_usd"] == 200500.0 and s["sells_under_10b5_1_plans"] == 1


def test_form4_xml_path_strips_stylesheet_prefix():
    assert insiders._xml_document("xslF345X05/wk-form4_1.xml") == "wk-form4_1.xml"
    assert insiders._xml_document("form4.xml") == "form4.xml"


def test_cboe_chain_parsing_and_summary():
    def opt(sym, oi, vol, iv, last):
        return {
            "option": sym,
            "open_interest": oi,
            "volume": vol,
            "iv": iv,
            "last_trade_price": last,
            "bid": 0,
            "ask": 0,
        }

    payload = {
        "data": {
            "current_price": 100.0,
            "options": [
                opt("AAPL261016C00100000", 500, 900, 0.30, 3.0),
                opt("AAPL261016C00110000", 300, 100, 0.25, 0.5),
                opt("AAPL261016P00100000", 800, 1200, 0.32, 2.5),
                opt("AAPL261016P00090000", 400, 50, 0.40, 0.4),
                opt("junk", 1, 1, 0.1, 1),
            ],
        }
    }
    spot, chains = options.parse_cboe(payload)
    assert spot == 100.0 and list(chains) == ["2026-10-16"]
    assert sorted(chains["2026-10-16"]["calls"]["strike"]) == [100.0, 110.0]
    exp = options.summarize(spot, chains)["expirations"][0] if date.today() <= date(2026, 10, 16) else None
    if exp:
        assert exp["put_call_volume_ratio"] == pytest.approx(1250 / 1000)
        assert exp["implied_move_pct"] == pytest.approx(0.055)


def test_fred_csv_newest_first_and_skips_missing():
    text = "observation_date,DGS10\n2026-09-24,4.10\n2026-09-25,.\n2026-09-26,4.20\n"
    assert economy.parse_fred_csv(text) == [{"date": "2026-09-26", "value": 4.2}, {"date": "2026-09-24", "value": 4.1}]


def test_rss_parsing_filters_old_items():
    xml = """<rss><channel>
      <item><title>Apple &amp; partners launch X</title><pubDate>Mon, 28 Sep 2026 14:00:00 GMT</pubDate>
        <description>&lt;p&gt;Details here&lt;/p&gt;</description><source url="x">Reuters</source></item>
      <item><title>Old story</title><pubDate>Mon, 01 Jun 2026 14:00:00 GMT</pubDate></item>
    </channel></rss>"""
    items = news.parse_rss(xml, now=datetime(2026, 9, 29, tzinfo=UTC))
    assert items == [
        {"date": "2026-09-28", "source": "Reuters", "headline": "Apple & partners launch X", "summary": "Details here"}
    ]


@pytest.mark.parametrize(
    ("sic", "sector"),
    [(3571, "Technology"), (2834, "Healthcare"), (6798, "Real Estate"), (6022, "Financial Services"), (None, None)],
)
def test_sic_to_sector(sic, sector):
    assert sec.sector_for_sic(sic) == sector
