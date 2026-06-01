"""Exit engine priority-ordering tests."""

from datetime import date

import config
from handlers.exit_engine import ExitEngine
from handlers.position_manager import PositionManager
from handlers.risk_manager import RiskManager


class _StubData:
    def __init__(self, ind_by_symbol):
        self._by = ind_by_symbol

    def get_indicators(self, symbol):
        return self._by.get(symbol)


def test_stop_loss_full_exit(mock_algorithm, mock_indicators):
    pm = PositionManager(mock_algorithm)
    pm.open_position("AAPL", 100.0, 10, date(2024, 1, 1))
    rm = RiskManager(mock_algorithm)

    ind = mock_indicators(close=90.0)  # 10% below entry -> > STOP_LOSS_PCT=7%
    engine = ExitEngine(mock_algorithm, pm, rm, _StubData({"AAPL": ind}))
    decisions = engine.generate_exits()
    assert len(decisions) == 1
    assert decisions[0].kind == "FULL"
    assert decisions[0].reason == config.EXIT_REASON_STOP_LOSS


def test_sma_breakdown_full_exit(mock_algorithm, mock_indicators):
    pm = PositionManager(mock_algorithm)
    pm.open_position("AAPL", 100.0, 10, date(2024, 1, 1))
    rm = RiskManager(mock_algorithm)

    # close below sma50 but not breaching stop-loss
    ind = mock_indicators(close=99.0, sma50=100.0, ema21=99.5)
    engine = ExitEngine(mock_algorithm, pm, rm, _StubData({"AAPL": ind}))
    decisions = engine.generate_exits()
    assert decisions[0].reason == config.EXIT_REASON_SMA_BREAKDOWN


def test_stretch_trim_partial(mock_algorithm, mock_indicators):
    pm = PositionManager(mock_algorithm)
    pm.open_position("AAPL", 100.0, 10, date(2024, 1, 1))
    rm = RiskManager(mock_algorithm)

    ind = mock_indicators(
        close=120.0, sma50=100.0, ema21=110.0,
        atr_stretch_low=config.WEBBY_RSI_STRETCH_LEVEL + 1.0,
    )
    engine = ExitEngine(mock_algorithm, pm, rm, _StubData({"AAPL": ind}))
    decisions = engine.generate_exits()
    kinds = {d.kind for d in decisions}
    assert "PARTIAL" in kinds
    partial = next(d for d in decisions if d.kind == "PARTIAL")
    assert partial.reason == config.EXIT_REASON_STRETCH_TRIM
    assert partial.quantity == 5  # 50% of 10


def test_drawdown_forces_liquidation_everywhere(mock_algorithm, mock_indicators):
    mock_algorithm.portfolio.cash = 100_000.0
    pm = PositionManager(mock_algorithm)
    pm.open_position("AAPL", 100.0, 10, date(2024, 1, 1))
    pm.open_position("MSFT", 200.0, 5, date(2024, 1, 1))
    rm = RiskManager(mock_algorithm)
    # Crash equity to breach DD
    mock_algorithm.portfolio.cash = 50_000.0

    ind = {"AAPL": mock_indicators(), "MSFT": mock_indicators()}
    engine = ExitEngine(mock_algorithm, pm, rm, _StubData(ind))
    decisions = engine.generate_exits()
    assert {d.reason for d in decisions} == {config.EXIT_REASON_DRAWDOWN}
    assert {d.symbol for d in decisions} == {"AAPL", "MSFT"}
