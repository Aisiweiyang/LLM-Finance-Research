import numpy as np
import pandas as pd
import pytest

from llm_finance.events import EventConfig, event_study


@pytest.fixture
def market():
    rng = np.random.default_rng(8)
    dates = pd.bdate_range("2024-01-01", periods=210)
    m = rng.normal(0, .01, len(dates))
    noise = rng.normal(0, .003, len(dates))
    y = .0002 + 1.2 * m + noise
    y[160] += .05
    prices = pd.concat([pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "ticker": ticker,
                                     "adjusted_close": 100 * np.exp(np.cumsum(values))})
                        for ticker, values in [("MKT", m), ("FIRM", y)]])
    events = pd.DataFrame([{"event_id": "shock", "event_date": str(dates[160].date()), "ticker": "FIRM"}])
    return dates, m, y, prices, events


def test_car_and_prediction_variance_against_independent_formula(market):
    dates, m, y, prices, events = market
    cfg = EventConfig(benchmark="MKT", window_start=-1, window_end=1)
    result, rejected = event_study(prices, events, cfg)
    # Work directly from known synthetic returns, separately from price-table code.
    mx, yy = m[30:150], y[30:150]
    beta = np.cov(mx, yy, ddof=1)[0, 1] / np.var(mx, ddof=1)
    alpha = yy.mean() - beta * mx.mean()
    expected = np.sum(y[159:162] - alpha - beta * m[159:162])
    sigma2 = np.sum((yy - alpha - beta * mx) ** 2) / 118
    expected_variance = sigma2 * (3 + 9 / 120 + (m[159:162].sum() - 3 * mx.mean()) ** 2 / np.sum((mx - mx.mean()) ** 2))
    assert rejected.empty
    assert result.iloc[0].car == pytest.approx(expected, abs=1e-12)
    assert result.iloc[0].car_se ** 2 == pytest.approx(expected_variance, abs=1e-14)
    assert result.iloc[0].car > .03


def test_missing_session_is_rejected_instead_of_compressed(market):
    dates, _, _, prices, events = market
    missing = prices[~((prices.ticker == "FIRM") & (prices.date == str(dates[159].date())))]
    result, rejected = event_study(missing, events, EventConfig(benchmark="MKT", window_start=-1, window_end=1))
    assert result.empty
    assert rejected.iloc[0].reason == "missing_session_return"


def test_weekend_rolls_to_next_market_session(market):
    dates, _, _, prices, _ = market
    monday = next(d for d in dates[150:] if d.weekday() == 0)
    events = pd.DataFrame([{"event_id": "weekend", "event_date": str((monday - pd.Timedelta(days=1)).date()), "ticker": "FIRM"}])
    result, _ = event_study(prices, events, EventConfig(benchmark="MKT"))
    assert result.iloc[0].event_session == str(monday.date())


def test_overlap_and_missing_proxy_are_recorded(market):
    dates, _, _, prices, events = market
    extra = pd.DataFrame([{"event_id": "overlap", "event_date": str(dates[161].date()), "ticker": "FIRM"},
                          {"event_id": "missing", "event_date": str(dates[161].date()), "ticker": "UNKNOWN"}])
    result, rejected = event_study(prices, pd.concat([events, extra]), EventConfig(benchmark="MKT"))
    assert len(result) == 1
    assert set(rejected.reason) == {"overlapping_event_window", "missing_ticker"}


def test_duplicate_keys_and_overlapping_estimation_fail(market):
    _, _, _, prices, events = market
    with pytest.raises(ValueError, match="Duplicate"):
        event_study(pd.concat([prices, prices.iloc[:1]]), events)
    with pytest.raises(ValueError, match="overlap"):
        EventConfig(gap_sessions=2, window_start=-10)

