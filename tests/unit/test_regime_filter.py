"""tests/unit/test_regime_filter.py — QQQ Power Trend state machine."""

from datetime import datetime, timedelta

import config
from handlers.regime_filter import RegimeFilter


def _ind(low, ema21, sma50, prior_sma50, close, is_blue_bar=True):
    return {
        "low": low, "EMA21": ema21, "SMA50": sma50,
        "prior_SMA50": prior_sma50, "close": close,
        "is_blue_bar": is_blue_bar,
    }


def _advance(algo):
    algo.time = algo.time + timedelta(days=1)


def _feed_uptrend(rf, algo, days, ema21=110.0, sma50=100.0, prior_sma50=99.5):
    """Drive QQQ low>EMA21 & EMA21>SMA50 for *days* bars."""
    for _ in range(days):
        _advance(algo)
        rf.update(_ind(low=ema21 + 0.5, ema21=ema21, sma50=sma50,
                       prior_sma50=prior_sma50, close=ema21 + 1.0,
                       is_blue_bar=True))


class TestActivation:
    def test_strict_activation_after_min_counters(self, mock_algorithm):
        mock_algorithm.time = datetime(2025, 1, 1)
        rf = RegimeFilter(mock_algorithm)
        needed = max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS)
        _feed_uptrend(rf, mock_algorithm, days=needed)
        assert rf.current_state == config.REGIME_TREND_UP
        assert rf.entries_allowed() is True

    def test_red_bar_blocks_activation_when_required(self, mock_algorithm):
        if not config.REQUIRE_ACTIVATION_UPDAY:
            return  # lite mode — skip
        mock_algorithm.time = datetime(2025, 1, 1)
        rf = RegimeFilter(mock_algorithm)
        needed = max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS)
        # All but last day blue; final activation bar is red.
        _feed_uptrend(rf, mock_algorithm, days=needed - 1)
        _advance(mock_algorithm)
        rf.update(_ind(low=110.5, ema21=110.0, sma50=100.0,
                       prior_sma50=99.5, close=111.0, is_blue_bar=False))
        assert rf.current_state == config.REGIME_NO_TREND
        assert rf.entries_allowed() is False

    def test_sma50_not_rising_blocks_when_required(self, mock_algorithm):
        if not config.REQUIRE_SMA50_RISING:
            return
        mock_algorithm.time = datetime(2025, 1, 1)
        rf = RegimeFilter(mock_algorithm)
        needed = max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS)
        for _ in range(needed):
            _advance(mock_algorithm)
            # prior_sma50 >= sma50 → not rising
            rf.update(_ind(low=110.5, ema21=110.0, sma50=100.0,
                           prior_sma50=100.0, close=111.0, is_blue_bar=True))
        assert rf.current_state == config.REGIME_NO_TREND


class TestTrendPressure:
    def test_close_below_sma50_with_ema_above_enters_pressure(self, mock_algorithm):
        if not config.ENABLE_TREND_PRESSURE:
            return
        mock_algorithm.time = datetime(2025, 1, 1)
        rf = RegimeFilter(mock_algorithm)
        _feed_uptrend(rf, mock_algorithm,
                      days=max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS))
        assert rf.current_state == config.REGIME_TREND_UP
        # Close drops below SMA50 but EMA still above SMA.
        _advance(mock_algorithm)
        rf.update(_ind(low=95.0, ema21=110.0, sma50=100.0,
                       prior_sma50=99.5, close=99.0, is_blue_bar=False))
        assert rf.current_state == config.REGIME_TREND_PRESSURE
        assert rf.entries_allowed() is False

    def test_pressure_re_arms_when_close_back_above_ema(self, mock_algorithm):
        if not config.ENABLE_TREND_PRESSURE:
            return
        mock_algorithm.time = datetime(2025, 1, 1)
        rf = RegimeFilter(mock_algorithm)
        _feed_uptrend(rf, mock_algorithm,
                      days=max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS))
        _advance(mock_algorithm)
        rf.update(_ind(low=95.0, ema21=110.0, sma50=100.0,
                       prior_sma50=99.5, close=99.0, is_blue_bar=False))
        # Re-arm.
        _advance(mock_algorithm)
        rf.update(_ind(low=110.5, ema21=110.0, sma50=100.0,
                       prior_sma50=99.5, close=112.0, is_blue_bar=True))
        assert rf.current_state == config.REGIME_TREND_UP


class TestTrendEnd:
    def test_ema_below_sma_triggers_trend_end(self, mock_algorithm):
        mock_algorithm.time = datetime(2025, 1, 1)
        rf = RegimeFilter(mock_algorithm)
        _feed_uptrend(rf, mock_algorithm,
                      days=max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS))
        _advance(mock_algorithm)
        rf.update(_ind(low=80.0, ema21=99.0, sma50=100.0,
                       prior_sma50=100.0, close=85.0, is_blue_bar=False))
        assert rf.current_state == config.REGIME_TREND_END
        assert rf.entries_allowed() is False
