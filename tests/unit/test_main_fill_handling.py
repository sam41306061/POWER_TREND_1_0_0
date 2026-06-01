"""Regression tests for main.py fill handling (Bug C1) and universe
auto-liquidation prevention (Bug C2).

These exercise the on_order_event + on_securities_changed callbacks without
running the full QC algo lifecycle.
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import config
from handlers.position_manager import PositionManager
from handlers.universe_filter import DynamicUniverseSelector


def _make_algo_with_handlers(mock_algorithm):
    """Build a PowerTrendAlgo-like object with the minimum wiring needed for
    on_order_event() to run, bypassing QC's initialize() lifecycle."""
    import main as main_mod

    algo = main_mod.PowerTrendAlgo.__new__(main_mod.PowerTrendAlgo)
    # Borrow stub fields from mock_algorithm
    algo.time = mock_algorithm.time
    algo.portfolio = mock_algorithm.portfolio
    algo.securities = mock_algorithm.securities
    algo.log = MagicMock()
    algo.debug = MagicMock()
    algo.error = MagicMock()
    algo._pending_orders = {}
    algo._positions = PositionManager(algo)
    algo._universe = DynamicUniverseSelector(algo)
    return algo


def _fill_event(order_id, symbol, qty, price, status_name="Filled"):
    """Mimic QC's OrderEvent. Status is a SimpleNamespace whose ``.name``
    attribute holds the string — matches both QC PascalCase ('Filled') and
    the test stub UPPER_CASE ('FILLED') paths because we lowercase before
    comparing."""
    return SimpleNamespace(
        order_id=order_id,
        symbol=symbol,
        fill_price=price,
        fill_quantity=qty,
        status=SimpleNamespace(name=status_name),
    )


# ---------------------------------------------------------------------------
# Bug C1 — on_order_event must record fills into PositionManager
# ---------------------------------------------------------------------------


def test_on_order_event_records_initial_fill(mock_algorithm):
    """Regression: previously, OrderStatus comparison used UPPER_CASE which
    didn't match QC's PascalCase enum, so every fill was silently dropped and
    _trades stayed empty for the entire backtest."""
    algo = _make_algo_with_handlers(mock_algorithm)
    algo._pending_orders[42] = {
        "type": "entry", "kind": "INITIAL", "symbol": "AAPL", "quantity": 10,
    }
    algo.on_order_event(_fill_event(42, "AAPL", 10, 150.0, status_name="Filled"))
    assert algo._positions.has_position("AAPL")


def test_on_order_event_handles_stub_upper_case_status(mock_algorithm):
    """Same handler must also work with the test stub's UPPER_CASE enum so the
    unit tests don't drift from production behaviour."""
    algo = _make_algo_with_handlers(mock_algorithm)
    algo._pending_orders[7] = {
        "type": "entry", "kind": "INITIAL", "symbol": "MSFT", "quantity": 5,
    }
    algo.on_order_event(_fill_event(7, "MSFT", 5, 300.0, status_name="FILLED"))
    assert algo._positions.has_position("MSFT")


def test_on_order_event_ignores_non_filled_status(mock_algorithm):
    algo = _make_algo_with_handlers(mock_algorithm)
    algo._pending_orders[3] = {
        "type": "entry", "kind": "INITIAL", "symbol": "AAPL", "quantity": 10,
    }
    algo.on_order_event(_fill_event(3, "AAPL", 10, 150.0, status_name="Submitted"))
    assert not algo._positions.has_position("AAPL")
    # Intent still queued (not popped).
    assert 3 in algo._pending_orders


def test_on_order_event_records_close_and_releases_universe(mock_algorithm):
    algo = _make_algo_with_handlers(mock_algorithm)
    # Open then close via on_order_event.
    algo._pending_orders[1] = {
        "type": "entry", "kind": "INITIAL", "symbol": "AAPL", "quantity": 10,
    }
    algo.on_order_event(_fill_event(1, "AAPL", 10, 100.0))
    algo._universe.retain_symbol("AAPL")
    assert "AAPL" in algo._universe.current_universe

    algo._pending_orders[2] = {
        "type": "exit", "kind": "FULL", "symbol": "AAPL",
        "quantity": 10, "reason": config.EXIT_REASON_STOP_LOSS,
    }
    algo.on_order_event(_fill_event(2, "AAPL", 10, 90.0))
    assert not algo._positions.has_position("AAPL")
    # Retention released; symbol no longer pinned.
    assert "AAPL" not in algo._universe._retained


def test_on_order_event_untracked_fill_logs_diagnostic(mock_algorithm):
    """A fill for an order we didn't queue (e.g. QC auto-liquidation) must
    surface a debug log, not silently no-op."""
    algo = _make_algo_with_handlers(mock_algorithm)
    algo.on_order_event(_fill_event(999, "AAPL", 10, 90.0))
    assert algo.debug.called
    msg = algo.debug.call_args[0][0]
    assert "[FILL UNTRACKED]" in msg


# ---------------------------------------------------------------------------
# Bug C2 — on_securities_changed pins held positions in universe
# ---------------------------------------------------------------------------


def test_on_securities_changed_retains_held_positions(mock_algorithm):
    algo = _make_algo_with_handlers(mock_algorithm)
    algo._positions.open_position("AAPL", 100.0, 10, date(2024, 1, 1))
    changes = SimpleNamespace(
        added_securities=[],
        removed_securities=[SimpleNamespace(symbol="AAPL"), SimpleNamespace(symbol="XYZ")],
    )
    algo.on_securities_changed(changes)
    # AAPL pinned; XYZ (not held) is not pinned.
    assert "AAPL" in algo._universe._retained
    assert "XYZ" not in algo._universe._retained
