"""Unit tests for handlers.exit_engine.ExitEngine and risk_manager.RiskManager."""

from datetime import date

import config
from handlers.exit_engine import ExitEngine
from handlers.position_manager import PositionManager
from handlers.risk_manager import RiskManager


def _ind(close=110, ema=105, sma=100, high_vs_sma10=0.0):
    return {"close": close, "EMA21": ema, "SMA50": sma, "high_vs_sma10": high_vs_sma10}


def _trade(algo, avg_price=100.0, qty=10):
    pm = PositionManager(algo)
    pm.add_leg("X", avg_price, qty, date(2024, 1, 1))
    return pm.get_trade("X")


def test_no_exit_when_all_clear(algo):
    risk = RiskManager(algo)
    risk.update(100_000)
    eng = ExitEngine(algo, risk)
    out, reason = eng.check(_trade(algo), _ind())
    assert out is False
    assert reason is None


def test_drawdown_exit_takes_priority(algo):
    risk = RiskManager(algo)
    risk.update(100_000)
    risk.update(100_000 * (1 - config.MAX_ACCOUNT_DRAWDOWN_PCT - 0.01))
    eng = ExitEngine(algo, risk)
    out, reason = eng.check(_trade(algo), _ind(close=50, ema=40, sma=30))
    assert out is True
    assert reason == config.EXIT_REASON_DRAWDOWN


def test_stop_loss_exit(algo):
    risk = RiskManager(algo)
    risk.update(100_000)
    eng = ExitEngine(algo, risk)
    stop_price = 100.0 * (1 - config.STOP_LOSS_PCT) - 0.01
    out, reason = eng.check(_trade(algo, avg_price=100), _ind(close=stop_price))
    assert out is True
    assert reason == config.EXIT_REASON_STOP_LOSS


def test_sma_breakdown_exit(algo):
    risk = RiskManager(algo)
    risk.update(100_000)
    eng = ExitEngine(algo, risk)
    out, reason = eng.check(_trade(algo), _ind(close=99, ema=105, sma=100))
    assert out is True
    assert reason == config.EXIT_REASON_SMA_BREAKDOWN


def test_ema_cross_exit(algo):
    risk = RiskManager(algo)
    risk.update(100_000)
    eng = ExitEngine(algo, risk)
    # close above sma but ema < sma
    out, reason = eng.check(_trade(algo), _ind(close=101, ema=99, sma=100))
    assert out is True
    assert reason == config.EXIT_REASON_EMA_CROSS


# ----------------------------------------------------------------------
# check_partial tests
# ----------------------------------------------------------------------


def test_partial_trim_fires_at_stretch_level(algo):
    risk = RiskManager(algo)
    risk.update(100_000)
    eng = ExitEngine(algo, risk)
    should_trim, reason = eng.check_partial(
        _trade(algo), _ind(high_vs_sma10=config.WEBBY_RSI_STRETCH_LEVEL)
    )
    assert should_trim is True
    assert reason == config.EXIT_REASON_STRETCH_TRIM


def test_partial_trim_does_not_fire_below_stretch_level(algo):
    risk = RiskManager(algo)
    risk.update(100_000)
    eng = ExitEngine(algo, risk)
    should_trim, reason = eng.check_partial(
        _trade(algo), _ind(high_vs_sma10=config.WEBBY_RSI_STRETCH_LEVEL - 0.01)
    )
    assert should_trim is False
    assert reason is None


def test_partial_trim_returns_false_on_empty_indicators(algo):
    risk = RiskManager(algo)
    risk.update(100_000)
    eng = ExitEngine(algo, risk)
    should_trim, reason = eng.check_partial(_trade(algo), {})
    assert should_trim is False
    assert reason is None


# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# Fallback stop-loss tests (indicators unavailable)
# ----------------------------------------------------------------------


def test_stop_loss_fires_via_last_known_price_when_no_indicators(algo):
    """Stop loss must fire using last_known_price when indicator data is unavailable."""
    risk = RiskManager(algo)
    risk.update(100_000)
    eng = ExitEngine(algo, risk)
    trade = _trade(algo, avg_price=100.0)
    trade.last_known_price = 100.0 * (1 - config.STOP_LOSS_PCT) - 0.01  # just below stop
    out, reason = eng.check(trade, None)
    assert out is True
    assert reason == config.EXIT_REASON_STOP_LOSS


def test_no_exit_via_last_known_price_when_above_stop(algo):
    """No exit when last_known_price is above the stop threshold and indicators are None."""
    risk = RiskManager(algo)
    risk.update(100_000)
    eng = ExitEngine(algo, risk)
    trade = _trade(algo, avg_price=100.0)
    trade.last_known_price = 100.0 * (1 - config.STOP_LOSS_PCT) + 1.0  # comfortably above stop
    out, reason = eng.check(trade, None)
    assert out is False
    assert reason is None


# ----------------------------------------------------------------------


def test_risk_manager_tracks_hwm(algo):
    risk = RiskManager(algo)
    risk.update(100_000)
    risk.update(120_000)
    risk.update(110_000)
    assert risk.hwm == 120_000
    assert abs(risk.drawdown - (10_000 / 120_000)) < 1e-9
    assert risk.is_new_entry_allowed() is True


def test_risk_manager_blocks_at_threshold(algo):
    risk = RiskManager(algo)
    risk.update(100_000)
    risk.update(100_000 * (1 - config.MAX_ACCOUNT_DRAWDOWN_PCT))
    assert risk.is_new_entry_allowed() is False
