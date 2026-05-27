"""tests/unit/test_exit_engine.py — Per-stock exit rule priority order."""

from dataclasses import dataclass

import config
from handlers.exit_engine import ExitEngine


@dataclass
class _MockTrade:
    total_quantity: int = 100
    avg_entry_price: float = 100.0


def _ind(close=110.0, sma50=105.0, ema21=107.0, high_vs_sma10=0.5):
    return {
        "close": close, "SMA50": sma50, "EMA21": ema21,
        "high_vs_sma10": high_vs_sma10,
    }


class TestPartial:
    def test_fires_at_stretch_threshold(self, mock_algorithm):
        ee = ExitEngine(mock_algorithm)
        trade = _MockTrade(total_quantity=100)
        ind = _ind(high_vs_sma10=config.WEBBY_RSI_STRETCH_LEVEL)
        out = ee.check_partial(trade, ind)
        assert out is not None
        assert out["quantity"] == int(100 * config.PARTIAL_EXIT_TRIM_FRACTION)
        assert out["reason"] == config.EXIT_REASON_STRETCH_TRIM

    def test_no_partial_below_threshold(self, mock_algorithm):
        ee = ExitEngine(mock_algorithm)
        trade = _MockTrade()
        ind = _ind(high_vs_sma10=config.WEBBY_RSI_STRETCH_LEVEL - 0.5)
        assert ee.check_partial(trade, ind) is None

    def test_returns_none_when_trim_qty_zero(self, mock_algorithm):
        ee = ExitEngine(mock_algorithm)
        trade = _MockTrade(total_quantity=1)
        ind = _ind(high_vs_sma10=config.WEBBY_RSI_STRETCH_LEVEL)
        # floor(1 * 0.5) = 0
        assert ee.check_partial(trade, ind) is None


class TestFullPriority:
    def test_priority_1_drawdown_wins_over_all(self, mock_algorithm):
        ee = ExitEngine(mock_algorithm)
        trade = _MockTrade(avg_entry_price=100.0)
        # Set up multiple triggers; drawdown must win.
        ind = _ind(close=50.0, sma50=60.0, ema21=55.0)
        out = ee.check_full(trade, ind, drawdown_breached=True)
        assert out == config.EXIT_REASON_DRAWDOWN

    def test_priority_2_stop_loss(self, mock_algorithm):
        ee = ExitEngine(mock_algorithm)
        trade = _MockTrade(avg_entry_price=100.0)
        stop_price = 100.0 * (1.0 - config.STOP_LOSS_PCT)
        ind = _ind(close=stop_price, sma50=80.0, ema21=85.0)
        out = ee.check_full(trade, ind, drawdown_breached=False)
        assert out == config.EXIT_REASON_STOP_LOSS

    def test_priority_3_target_profit(self, mock_algorithm):
        ee = ExitEngine(mock_algorithm)
        trade = _MockTrade(avg_entry_price=100.0)
        target_price = 100.0 * (1.0 + config.TARGET_PROFIT_PCT)
        ind = _ind(close=target_price, sma50=80.0, ema21=85.0)
        out = ee.check_full(trade, ind, drawdown_breached=False)
        assert out == config.EXIT_REASON_TARGET_PROFIT

    def test_priority_4_sma_breakdown(self, mock_algorithm):
        ee = ExitEngine(mock_algorithm)
        trade = _MockTrade(avg_entry_price=100.0)
        ind = _ind(close=99.0, sma50=100.0, ema21=101.0)
        out = ee.check_full(trade, ind, drawdown_breached=False)
        assert out == config.EXIT_REASON_SMA_BREAKDOWN

    def test_priority_5_ema_cross(self, mock_algorithm):
        ee = ExitEngine(mock_algorithm)
        trade = _MockTrade(avg_entry_price=100.0)
        # Close > sma50 so SMA breakdown doesn't fire; ema21 < sma50.
        ind = _ind(close=110.0, sma50=100.0, ema21=99.0)
        out = ee.check_full(trade, ind, drawdown_breached=False)
        assert out == config.EXIT_REASON_EMA_CROSS

    def test_no_exit_when_all_clear(self, mock_algorithm):
        ee = ExitEngine(mock_algorithm)
        trade = _MockTrade(avg_entry_price=100.0)
        ind = _ind(close=105.0, sma50=100.0, ema21=102.0)
        assert ee.check_full(trade, ind, drawdown_breached=False) is None
