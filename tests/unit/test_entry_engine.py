"""tests/unit/test_entry_engine.py — Per-stock entry rules."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from handlers.entry_engine import EntryEngine


@dataclass
class _MockTrade:
    last_leg_date: Optional[date] = None


def _ind(close=110.0, ema21=105.0, sma50=100.0,
         prior_low=104.0, prior_ema21=105.0, is_blue_bar=True):
    return {
        "close": close, "EMA21": ema21, "SMA50": sma50,
        "prior_low": prior_low, "prior_EMA21": prior_ema21,
        "is_blue_bar": is_blue_bar,
    }


class TestInitialEntry:
    def test_happy_path(self, mock_algorithm):
        ee = EntryEngine(mock_algorithm)
        assert ee.check_initial(_ind()) is True

    def test_rejects_when_stack_broken(self, mock_algorithm):
        ee = EntryEngine(mock_algorithm)
        assert ee.check_initial(_ind(close=99.0)) is False  # close < ema21
        assert ee.check_initial(_ind(ema21=99.0)) is False  # ema21 < sma50

    def test_rejects_when_no_pullback(self, mock_algorithm):
        ee = EntryEngine(mock_algorithm)
        # prior_low > prior_EMA21 → no pullback
        assert ee.check_initial(_ind(prior_low=106.0, prior_ema21=105.0)) is False

    def test_rejects_red_bar(self, mock_algorithm):
        ee = EntryEngine(mock_algorithm)
        assert ee.check_initial(_ind(is_blue_bar=False)) is False

    def test_returns_false_on_none(self, mock_algorithm):
        ee = EntryEngine(mock_algorithm)
        assert ee.check_initial(None) is False


class TestAddon:
    def test_happy_path_new_pullback_after_last_leg(self, mock_algorithm):
        mock_algorithm.time = datetime(2025, 2, 1)
        ee = EntryEngine(mock_algorithm)
        trade = _MockTrade(last_leg_date=date(2025, 1, 15))
        assert ee.check_addon(trade, _ind()) is True

    def test_rejects_when_no_pullback(self, mock_algorithm):
        mock_algorithm.time = datetime(2025, 2, 1)
        ee = EntryEngine(mock_algorithm)
        trade = _MockTrade(last_leg_date=date(2025, 1, 15))
        assert ee.check_addon(trade, _ind(prior_low=106.0)) is False

    def test_rejects_same_day_as_last_leg(self, mock_algorithm):
        mock_algorithm.time = datetime(2025, 1, 15)
        ee = EntryEngine(mock_algorithm)
        trade = _MockTrade(last_leg_date=date(2025, 1, 15))
        assert ee.check_addon(trade, _ind()) is False

    def test_rejects_red_bar(self, mock_algorithm):
        mock_algorithm.time = datetime(2025, 2, 1)
        ee = EntryEngine(mock_algorithm)
        trade = _MockTrade(last_leg_date=date(2025, 1, 15))
        assert ee.check_addon(trade, _ind(is_blue_bar=False)) is False

    def test_returns_false_when_trade_none(self, mock_algorithm):
        ee = EntryEngine(mock_algorithm)
        assert ee.check_addon(None, _ind()) is False
