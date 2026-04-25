"""Unit tests for handlers.regime_filter.RegimeFilter (Power Trend state machine)."""

import config
from handlers.regime_filter import RegimeFilter


def _ind(close, open_, low, ema, sma, prior_sma):
    return {
        "close": close,
        "open": open_,
        "low": low,
        "EMA21": ema,
        "SMA50": sma,
        "prior_SMA50": prior_sma,
        "is_blue_bar": close >= open_,
    }


def _push_bullish(rf: RegimeFilter, days: int):
    """Drive counters up to satisfy activation thresholds with all conditions met."""
    sma_prev = 99.0
    for _ in range(days):
        sma_today = sma_prev + 0.1
        rf.update(_ind(close=110, open_=109, low=105, ema=104, sma=sma_today, prior_sma=sma_prev))
        sma_prev = sma_today


def test_strict_activation_after_thresholds(algo):
    rf = RegimeFilter(algo)
    _push_bullish(rf, max(config.LOW_ABOVE_EMA_DAYS, config.EMA_ABOVE_SMA_DAYS) + 1)
    assert rf.current_state == config.REGIME_TREND_UP
    assert rf.entries_allowed() is True


def test_red_bar_blocks_strict_activation(algo, monkeypatch):
    monkeypatch.setattr(config, "REQUIRE_ACTIVATION_UPDAY", True)
    rf = RegimeFilter(algo)
    # Build counters with red bars
    sma_prev = 99.0
    for _ in range(config.LOW_ABOVE_EMA_DAYS + 2):
        sma_today = sma_prev + 0.1
        rf.update(_ind(close=108, open_=110, low=105, ema=104, sma=sma_today, prior_sma=sma_prev))
        sma_prev = sma_today
    assert rf.current_state == config.REGIME_NO_TREND
    assert rf.entries_allowed() is False


def test_lite_mode_activation_without_blue_bar(algo, monkeypatch):
    monkeypatch.setattr(config, "REQUIRE_ACTIVATION_UPDAY", False)
    monkeypatch.setattr(config, "REQUIRE_SMA50_RISING", False)
    rf = RegimeFilter(algo)
    sma_prev = 99.0
    for _ in range(config.LOW_ABOVE_EMA_DAYS + 2):
        # red bar + flat SMA
        rf.update(_ind(close=108, open_=110, low=105, ema=104, sma=sma_prev, prior_sma=sma_prev))
    assert rf.current_state == config.REGIME_TREND_UP


def test_weak_market_no_trend(algo):
    rf = RegimeFilter(algo)
    rf.update(_ind(close=100, open_=99, low=98, ema=99, sma=100, prior_sma=100))
    assert rf.current_state == config.REGIME_NO_TREND
    assert rf.entries_allowed() is False


def test_trend_pressure_on_close_below_sma(algo, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_TREND_PRESSURE", True)
    rf = RegimeFilter(algo)
    _push_bullish(rf, config.LOW_ABOVE_EMA_DAYS + 2)
    assert rf.current_state == config.REGIME_TREND_UP

    # Close below SMA50 but EMA > SMA still
    rf.update(_ind(close=95, open_=96, low=94, ema=104, sma=100, prior_sma=99.5))
    assert rf.current_state == config.REGIME_TREND_PRESSURE
    assert rf.entries_allowed() is False


def test_pressure_rearm_to_trend_up(algo, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_TREND_PRESSURE", True)
    rf = RegimeFilter(algo)
    _push_bullish(rf, config.LOW_ABOVE_EMA_DAYS + 2)
    rf.update(_ind(close=95, open_=96, low=94, ema=104, sma=100, prior_sma=99.5))
    assert rf.current_state == config.REGIME_TREND_PRESSURE

    # Close back above EMA21, EMA still above SMA
    rf.update(_ind(close=110, open_=108, low=107, ema=104, sma=100, prior_sma=99.9))
    assert rf.current_state == config.REGIME_TREND_UP


def test_deactivation_on_ema_cross_below_sma(algo):
    rf = RegimeFilter(algo)
    _push_bullish(rf, config.LOW_ABOVE_EMA_DAYS + 2)
    assert rf.current_state == config.REGIME_TREND_UP

    rf.update(_ind(close=95, open_=96, low=94, ema=99, sma=100, prior_sma=100))
    assert rf.current_state == config.REGIME_TREND_END
    assert rf.entries_allowed() is False


def test_no_cooldown_reactivation(algo):
    rf = RegimeFilter(algo)
    _push_bullish(rf, config.LOW_ABOVE_EMA_DAYS + 2)
    rf.update(_ind(close=95, open_=96, low=94, ema=99, sma=100, prior_sma=100))
    assert rf.current_state == config.REGIME_TREND_END
    # Counters reset (low not above ema; ema not above sma) — bullish push re-activates
    _push_bullish(rf, config.LOW_ABOVE_EMA_DAYS + 2)
    assert rf.current_state == config.REGIME_TREND_UP
