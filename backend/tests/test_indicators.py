import numpy as np
import pandas as pd
import pytest

from app.data import indicators as ind


def series(values):
    return pd.Series(values, index=pd.date_range("2024-01-01", periods=len(values), freq="B"), dtype=float)


def test_sma_and_pct_change():
    s = series(range(1, 11))
    assert ind.sma(s, 5) == pytest.approx(8.0)
    assert ind.pct_change(s, 1) == pytest.approx(10 / 9 - 1)
    assert ind.sma(s, 50) is None


def test_rsi_extremes():
    assert ind.rsi(series(range(1, 40))) == pytest.approx(100.0)
    assert ind.rsi(series(range(40, 1, -1))) < 5


def test_max_drawdown():
    assert ind.max_drawdown(series([100, 120, 60, 90])) == pytest.approx(-0.5)


def test_beta_of_a_leveraged_copy_is_two():
    rng = np.random.default_rng(0)
    bench = series(100 * np.cumprod(1 + rng.normal(0, 0.01, 200)))
    stock = series(100 * np.cumprod(1 + 2 * bench.pct_change().fillna(0).to_numpy()))
    out = ind.beta_and_corr(stock, bench)
    assert out["beta"] == pytest.approx(2.0, rel=1e-6)
    assert out["correlation"] == pytest.approx(1.0, rel=1e-6)


def test_yoy():
    assert ind.yoy([100, 110, None, 50]) == [None, pytest.approx(0.1), None, None]


def chain(strikes, oi, volume=None, iv=0.3, last=1.0):
    return pd.DataFrame(
        {
            "strike": strikes,
            "openInterest": oi,
            "volume": volume or [0] * len(strikes),
            "impliedVolatility": [iv] * len(strikes),
            "lastPrice": [last] * len(strikes),
        }
    )


def test_max_pain_sits_where_open_interest_clusters():
    # Holders' payout at 90/100/110 is 30k/20k/30k, so writers "win" most at 100.
    calls = chain([90, 100, 110], [1000, 1000, 0])
    puts = chain([90, 100, 110], [0, 1000, 1000])
    assert ind.max_pain(calls, puts) == 100


def test_chain_summary_ratios_and_implied_move():
    calls = chain([95, 100, 105, 110], [100] * 4, volume=[50] * 4, iv=0.25, last=2.0)
    puts = chain([90, 95, 100, 105], [200] * 4, volume=[100] * 4, iv=0.35, last=3.0)
    out = ind.chain_summary(calls, puts, spot=100)
    assert out["put_call_volume_ratio"] == pytest.approx(2.0)
    assert out["put_call_oi_ratio"] == pytest.approx(2.0)
    assert out["implied_move_pct"] == pytest.approx(0.05)
    assert out["skew_10pct_otm_put_minus_call_iv"] == pytest.approx(0.10)


def test_unusual_activity_requires_volume_over_open_interest():
    df = chain([100, 105], [100, 5000], volume=[2000, 1000])
    assert [r["strike"] for r in ind.unusual_activity(df, "call")] == [100.0]
