"""Power Trend regime state machine tests."""

import config
from handlers.regime_filter import RegimeFilter


def _ind(low=100, close=102, prior_close=101, ema21=99, sma50=95,
         prior_ema21=99, prior_sma50=95, sma50_n_days_ago=94):
    return {
        "low": low, "close": close, "prior_close": prior_close,
        "ema21": ema21, "sma50": sma50,
        "prior_ema21": prior_ema21, "prior_sma50": prior_sma50,
        "sma50_n_days_ago": sma50_n_days_ago,
    }


def test_initial_state_is_no_trend(mock_algorithm):
    rf = RegimeFilter(mock_algorithm)
    assert rf.current_state == config.REGIME_NO_TREND
    assert not rf.entries_allowed()


def test_activation_requires_all_streaks(mock_algorithm):
    rf = RegimeFilter(mock_algorithm)
    # Feed enough bullish bars to satisfy both streaks
    for _ in range(max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS) + 2):
        rf.update(_ind())
    assert rf.current_state == config.REGIME_TREND_UP
    assert rf.entries_allowed()


def test_deactivation_on_ema21_below_sma50(mock_algorithm):
    rf = RegimeFilter(mock_algorithm)
    for _ in range(max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS) + 2):
        rf.update(_ind())
    assert rf.current_state == config.REGIME_TREND_UP

    # EMA21 drops below SMA50 → TREND_END (then to NO_TREND next bar)
    rf.update(_ind(ema21=90, sma50=95))
    assert rf.current_state == config.REGIME_TREND_END
    assert not rf.entries_allowed()


def test_trend_pressure_round_trip(mock_algorithm):
    rf = RegimeFilter(mock_algorithm)
    for _ in range(max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS) + 2):
        rf.update(_ind())
    assert rf.current_state == config.REGIME_TREND_UP

    # Low dips below EMA21 but EMA21 still above SMA50 → PRESSURE
    rf.update(_ind(low=95, ema21=99, sma50=95))
    assert rf.current_state == config.REGIME_TREND_PRESSURE
    assert rf.entries_allowed()  # entries still allowed in pressure

    # Low reclaims EMA21 → back to TREND_UP
    rf.update(_ind())
    assert rf.current_state == config.REGIME_TREND_UP
