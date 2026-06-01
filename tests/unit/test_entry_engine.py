"""Entry engine decision tests (initial + add-on)."""

from datetime import date

import config
from handlers.entry_engine import EntryEngine
from handlers.position_manager import PositionManager
from handlers.pyramiding_manager import PyramidingManager
from handlers.regime_filter import RegimeFilter
from handlers.risk_manager import RiskManager


class _StubData:
    def __init__(self, by_symbol):
        self._by = by_symbol

    def get_indicators(self, symbol):
        return self._by.get(symbol)


class _OpenRegime:
    """Stub regime that always allows entries."""
    def entries_allowed(self):
        return True


class _ClosedRegime:
    def entries_allowed(self):
        return False


def _build(algo, ind_map, regime=None):
    pm = PositionManager(algo)
    rm = RiskManager(algo)
    py = PyramidingManager(algo)
    data = _StubData(ind_map)
    eng = EntryEngine(
        algo, pm, regime or _OpenRegime(), rm, py, data
    )
    return eng, pm


def test_initial_entry_passes_filter(mock_algorithm, mock_indicators):
    mock_algorithm.portfolio.cash = 100_000.0
    ind = mock_indicators()
    engine, pm = _build(mock_algorithm, {"AAPL": ind})
    decisions = engine.generate_entries(["AAPL"])
    assert len(decisions) == 1
    assert decisions[0].kind == "INITIAL"
    assert decisions[0].target_quantity > 0


def test_initial_entry_blocked_when_regime_closed(mock_algorithm, mock_indicators):
    engine, _ = _build(
        mock_algorithm, {"AAPL": mock_indicators()}, regime=_ClosedRegime()
    )
    assert engine.generate_entries(["AAPL"]) == []


def test_initial_entry_requires_blue_bar(mock_algorithm, mock_indicators):
    ind = mock_indicators(is_blue_bar=False)
    engine, _ = _build(mock_algorithm, {"AAPL": ind})
    assert engine.generate_entries(["AAPL"]) == []


def test_initial_entry_requires_sma10_breakout(mock_algorithm, mock_indicators):
    # prior_close below SMA10 → fails the SMA10 breakout confirmation
    ind = mock_indicators(prior_close=149.0, sma10=150.0)
    engine, _ = _build(mock_algorithm, {"AAPL": ind})
    assert engine.generate_entries(["AAPL"]) == []


def test_addon_decision_for_existing_position(mock_algorithm, mock_indicators):
    mock_algorithm.portfolio.cash = 100_000.0
    ind = mock_indicators()
    engine, pm = _build(mock_algorithm, {"AAPL": ind})

    # Open position yesterday so it qualifies for an add-on today
    pm.open_position("AAPL", 100.0, 10, date(2023, 12, 31))
    decisions = engine.generate_entries([])  # universe empty -> only add-ons
    assert len(decisions) == 1
    assert decisions[0].kind == "ADD_ON"


def test_generate_entries_caps_initial_decisions_at_max_positions(
    mock_algorithm, mock_indicators
):
    """Regression: previously, can_add_position() reflected only settled
    on_order_event state, so a single generate_entries() call could append
    100+ INITIAL decisions on the first TREND_UP day."""
    mock_algorithm.portfolio.cash = 10_000_000.0
    universe = [f"SYM{i:03d}" for i in range(100)]
    ind_map = {s: mock_indicators() for s in universe}
    engine, _ = _build(mock_algorithm, ind_map)

    decisions = engine.generate_entries(universe)
    initials = [d for d in decisions if d.kind == "INITIAL"]
    assert len(initials) <= config.MAX_POSITIONS_OPEN
