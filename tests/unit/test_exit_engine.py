"""Unit tests for handlers.exit_engine.ExitEngine and risk_manager.RiskManager."""

from datetime import date, timedelta

import config
from handlers.exit_engine import ExitEngine
from handlers.position_manager import PositionManager
from handlers.risk_manager import RiskManager


def _ind(close=110, ema=105, sma=100):
    return {"close": close, "EMA21": ema, "SMA50": sma}


def _trade(algo, premium=5.0, contracts=10, expiry=None, contract_symbol="X_OPT"):
    if expiry is None:
        expiry = date(2024, 7, 19)
    pm = PositionManager(algo)
    pm.add_leg(
        symbol="X",
        fill_price=premium,
        quantity=contracts,
        fill_date=date(2024, 1, 1),
        contract_symbol=contract_symbol,
        expiry=expiry,
        strike=100.0,
        delta_at_entry=0.70,
    )
    return pm.get_trade("X")


def _eng(algo, equity=100_000):
    risk = RiskManager(algo)
    risk.update(equity)
    return ExitEngine(algo, risk), risk


def test_no_exit_when_all_clear(algo):
    eng, _ = _eng(algo)
    decisions = eng.check(_trade(algo), _ind(), today=date(2024, 1, 15))
    assert decisions == []


def test_drawdown_exit_takes_priority(algo):
    eng, risk = _eng(algo)
    risk.update(100_000 * (1 - config.MAX_ACCOUNT_DRAWDOWN_PCT - 0.01))
    decisions = eng.check(
        _trade(algo), _ind(close=50, ema=40, sma=30), today=date(2024, 1, 15)
    )
    assert decisions == [(None, config.EXIT_REASON_DRAWDOWN)]


def test_sma_breakdown_trade_wide(algo):
    eng, _ = _eng(algo)
    decisions = eng.check(
        _trade(algo), _ind(close=99, ema=105, sma=100), today=date(2024, 1, 15)
    )
    assert decisions == [(None, config.EXIT_REASON_SMA_BREAKDOWN)]


def test_ema_cross_trade_wide(algo):
    eng, _ = _eng(algo)
    decisions = eng.check(
        _trade(algo), _ind(close=101, ema=99, sma=100), today=date(2024, 1, 15)
    )
    assert decisions == [(None, config.EXIT_REASON_EMA_CROSS)]


def test_dte_force_close_per_leg(algo):
    eng, _ = _eng(algo)
    today = date(2024, 7, 5)
    expiry = today + timedelta(days=config.OPTION_FORCE_EXIT_DAYS_BEFORE_EXPIRY)
    trade = _trade(algo, expiry=expiry)
    decisions = eng.check(trade, _ind(), today=today)
    assert len(decisions) == 1
    leg, reason = decisions[0]
    assert reason == config.EXIT_REASON_DTE_FORCE
    assert leg is trade.legs[0]


def test_dte_force_close_only_offending_leg(algo):
    eng, _ = _eng(algo)
    today = date(2024, 7, 5)
    pm = PositionManager(algo)
    pm.add_leg("X", 5.0, 10, date(2024, 1, 1),
               contract_symbol="C1",
               expiry=today + timedelta(days=10),  # within 14d -> force
               strike=100, delta_at_entry=0.70)
    pm.add_leg("X", 6.0, 10, date(2024, 1, 5),
               contract_symbol="C2",
               expiry=today + timedelta(days=120),  # safe
               strike=110, delta_at_entry=0.70)
    trade = pm.get_trade("X")
    decisions = eng.check(trade, _ind(), today=today)
    assert len(decisions) == 1
    leg, reason = decisions[0]
    assert reason == config.EXIT_REASON_DTE_FORCE
    assert leg.contract_symbol == "C1"


def test_premium_stop_loss_per_leg(algo):
    eng, _ = _eng(algo)
    today = date(2024, 1, 15)
    trade = _trade(algo, premium=5.0, expiry=today + timedelta(days=180))
    # Premium has dropped to 50% of entry — should fire premium stop
    threshold = 5.0 * (1 - config.OPTION_PREMIUM_STOP_LOSS_PCT)
    decisions = eng.check(
        trade,
        _ind(),
        today=today,
        premium_lookup=lambda _: threshold,
    )
    assert len(decisions) == 1
    leg, reason = decisions[0]
    assert reason == config.EXIT_REASON_PREMIUM_STOP


def test_premium_stop_not_fired_when_above_threshold(algo):
    eng, _ = _eng(algo)
    today = date(2024, 1, 15)
    trade = _trade(algo, premium=5.0, expiry=today + timedelta(days=180))
    decisions = eng.check(
        trade, _ind(), today=today,
        premium_lookup=lambda _: 4.0,  # only 20% drop, above 50% stop
    )
    assert decisions == []


def test_dte_takes_precedence_over_premium_for_same_leg(algo):
    eng, _ = _eng(algo)
    today = date(2024, 7, 5)
    trade = _trade(algo, premium=5.0, expiry=today + timedelta(days=10))
    decisions = eng.check(
        trade, _ind(), today=today,
        premium_lookup=lambda _: 1.0,  # would also trigger premium stop
    )
    # Only one decision per leg; DTE evaluated first via continue
    assert len(decisions) == 1
    assert decisions[0][1] == config.EXIT_REASON_DTE_FORCE


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
