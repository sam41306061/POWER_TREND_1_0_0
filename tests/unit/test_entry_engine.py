"""Unit tests for handlers.entry_engine.EntryEngine."""

from datetime import date, timedelta

import config
from handlers.entry_engine import EntryEngine, EntrySignal
from handlers.position_manager import PositionManager
from handlers.pyramiding_manager import PyramidingManager
from handlers.regime_filter import RegimeFilter
from handlers.risk_manager import RiskManager


class _RegimeOn:
    def entries_allowed(self):
        return True


class _RegimeOff:
    def entries_allowed(self):
        return False


class _RiskOk:
    def is_new_entry_allowed(self):
        return True


class _RiskBlocked:
    def is_new_entry_allowed(self):
        return False


def _ind(close=110, open_=109, ema=105, sma=100, prior_low=99, prior_ema=100):
    return {
        "close": close,
        "open": open_,
        "EMA21": ema,
        "SMA50": sma,
        "prior_low": prior_low,
        "prior_EMA21": prior_ema,
        "is_blue_bar": close >= open_,
    }


def _engine(algo, regime, risk, pm=None):
    pm = pm or PositionManager(algo)
    pyr = PyramidingManager(algo)
    return EntryEngine(algo, regime, risk, pm, pyr), pm


def test_initial_entry_passes_all_gates(algo):
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk())
    assert eng.evaluate("AAPL", _ind()) == EntrySignal.INITIAL


def test_blocked_when_regime_off(algo):
    eng, _ = _engine(algo, _RegimeOff(), _RiskOk())
    assert eng.evaluate("AAPL", _ind()) is None


def test_blocked_when_risk_off(algo):
    eng, _ = _engine(algo, _RegimeOn(), _RiskBlocked())
    assert eng.evaluate("AAPL", _ind()) is None


def test_blocked_when_red_bar(algo):
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk())
    assert eng.evaluate("AAPL", _ind(close=108, open_=110)) is None


def test_blocked_when_no_pullback(algo):
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk())
    assert eng.evaluate("AAPL", _ind(prior_low=120, prior_ema=100)) is None


def test_blocked_when_not_bullish_stack(algo):
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk())
    # ema below sma
    assert eng.evaluate("AAPL", _ind(ema=99, sma=100)) is None


def test_blocked_at_position_capacity(algo):
    pm = PositionManager(algo)
    for i in range(config.MAX_POSITIONS_OPEN):
        pm.add_leg(f"S{i}", 50.0, 1, date(2024, 1, 1))
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk(), pm=pm)
    assert eng.evaluate("NEW", _ind()) is None


def test_add_signal_when_position_exists(algo):
    pm = PositionManager(algo)
    pm.add_leg("AAPL", 100.0, 10, fill_date=algo.time.date() - timedelta(days=5))
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk(), pm=pm)
    assert eng.evaluate("AAPL", _ind()) == EntrySignal.ADD


def test_add_blocked_when_pyramid_cap_reached(algo):
    pm = PositionManager(algo)
    for i in range(1 + config.PYRAMID_MAX_ADDS):
        pm.add_leg(
            "AAPL", 100.0, 10, fill_date=algo.time.date() - timedelta(days=10 - i)
        )
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk(), pm=pm)
    assert eng.evaluate("AAPL", _ind()) is None


def test_add_blocked_same_day_as_last_leg(algo):
    pm = PositionManager(algo)
    pm.add_leg("AAPL", 100.0, 10, fill_date=algo.time.date())
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk(), pm=pm)
    assert eng.evaluate("AAPL", _ind()) is None


def test_projected_open_count_blocks_initial_when_at_cap(algo):
    """When the orchestrator reports projected_open_count >= cap, INITIAL
    signals must be refused even though active_trades < cap (the gap is
    in-flight pending entries)."""
    pm = PositionManager(algo)
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk(), pm=pm)
    # Empty book, but caller signals the cap is already saturated by pending.
    result = eng.evaluate(
        "AAPL", _ind(), projected_open_count=config.MAX_POSITIONS_OPEN
    )
    assert result is None


def test_projected_open_count_allows_initial_below_cap(algo):
    pm = PositionManager(algo)
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk(), pm=pm)
    result = eng.evaluate(
        "AAPL", _ind(), projected_open_count=config.MAX_POSITIONS_OPEN - 1
    )
    assert result == EntrySignal.INITIAL


def test_projected_open_count_does_not_block_add_signals(algo):
    """ADD signals don't grow the trade count, so projected_open_count must
    not gate them."""
    pm = PositionManager(algo)
    pm.add_leg("AAPL", 100.0, 10, fill_date=date(2024, 1, 1))
    eng, _ = _engine(algo, _RegimeOn(), _RiskOk(), pm=pm)
    result = eng.evaluate(
        "AAPL", _ind(), projected_open_count=config.MAX_POSITIONS_OPEN + 5
    )
    assert result == EntrySignal.ADD
