"""tests/unit/test_risk_manager.py — HWM drawdown gate."""

import config
from handlers.risk_manager import RiskManager


class TestRiskManager:
    def test_hwm_starts_zero(self, mock_algorithm):
        rm = RiskManager(mock_algorithm)
        assert rm.high_water_mark == 0.0
        assert rm.drawdown == 0.0
        assert rm.is_new_entry_allowed() is True

    def test_hwm_bumps_on_new_high(self, mock_algorithm):
        rm = RiskManager(mock_algorithm)
        rm.update(100_000.0)
        rm.update(110_000.0)
        assert rm.high_water_mark == 110_000.0

    def test_drawdown_computation(self, mock_algorithm):
        rm = RiskManager(mock_algorithm)
        rm.update(100_000.0)
        rm.update(90_000.0)
        assert abs(rm.drawdown - 0.10) < 1e-9

    def test_entry_blocked_at_threshold(self, mock_algorithm):
        rm = RiskManager(mock_algorithm)
        rm.update(100_000.0)
        breach_equity = 100_000.0 * (1.0 - config.MAX_ACCOUNT_DRAWDOWN_PCT)
        rm.update(breach_equity)
        assert rm.is_new_entry_allowed() is False

    def test_entry_allowed_just_below_threshold(self, mock_algorithm):
        rm = RiskManager(mock_algorithm)
        rm.update(100_000.0)
        near_breach = 100_000.0 * (1.0 - config.MAX_ACCOUNT_DRAWDOWN_PCT + 0.001)
        rm.update(near_breach)
        assert rm.is_new_entry_allowed() is True

    def test_ignores_non_positive_equity(self, mock_algorithm):
        rm = RiskManager(mock_algorithm)
        rm.update(100_000.0)
        rm.update(0.0)
        rm.update(-50.0)
        assert rm.high_water_mark == 100_000.0
        assert rm.current_equity == 100_000.0
