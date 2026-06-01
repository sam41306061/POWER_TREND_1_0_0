"""Account-level risk manager tests."""

import config
from handlers.risk_manager import RiskManager


def test_initial_hwm_equals_portfolio_value(mock_algorithm):
    mock_algorithm.portfolio.cash = 100_000.0
    rm = RiskManager(mock_algorithm)
    assert rm.hwm == 100_000.0
    assert rm.current_drawdown == 0.0
    assert rm.is_new_entry_allowed()


def test_hwm_advances_with_equity(mock_algorithm):
    mock_algorithm.portfolio.cash = 100_000.0
    rm = RiskManager(mock_algorithm)
    mock_algorithm.portfolio.cash = 110_000.0
    rm.update()
    assert rm.hwm == 110_000.0


def test_drawdown_blocks_new_entries(mock_algorithm):
    mock_algorithm.portfolio.cash = 100_000.0
    rm = RiskManager(mock_algorithm)
    # Drop equity below threshold
    threshold = config.MAX_ACCOUNT_DRAWDOWN_PCT
    mock_algorithm.portfolio.cash = 100_000.0 * (1.0 - threshold - 0.01)
    assert not rm.is_new_entry_allowed()
