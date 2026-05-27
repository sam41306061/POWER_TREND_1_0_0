"""
tests/conftest.py — Pytest Configuration & Module Injection

Responsibility:
  1. Inject type_stubs into sys.modules as "AlgorithmImports"
     so handlers can "from AlgorithmImports import *" without LEAN SDK
  2. Provide shared fixtures for mock algorithm, history, trade records, etc.
  3. Run BEFORE any test file imports handlers

Running order:
  1. conftest.py executed
  2. sys.modules["AlgorithmImports"] = stub_module
  3. test files import handlers
  4. handlers import "from AlgorithmImports import *"
  5. Resolution: AlgorithmImports stubs, not LEAN SDK
"""

import sys
import types
import pytest
import pandas as pd
from datetime import datetime, timedelta

# Import type_stubs BEFORE injecting into sys.modules
try:
    import type_stubs
except ImportError:
    # type_stubs.py should be in project root
    raise ImportError("type_stubs.py not found in project root")


# ============================================================================
# MODULE INJECTION (must happen BEFORE any handler imports)
# ============================================================================

def inject_stub_module():
    """
    Inject type_stubs into sys.modules as "AlgorithmImports".
    This allows handlers to use "from AlgorithmImports import *"
    without requiring LEAN SDK.
    """
    stub_module = types.ModuleType("AlgorithmImports")
    for name in type_stubs.__all__:
        setattr(stub_module, name, getattr(type_stubs, name))
    sys.modules["AlgorithmImports"] = stub_module


# Inject before pytest collects test functions
inject_stub_module()


# ============================================================================
# SHARED FIXTURES
# ============================================================================

@pytest.fixture
def mock_algorithm():
    """
    Stub QCAlgorithm instance for testing.
    Pre-configured with sensible defaults.
    """
    from type_stubs import QCAlgorithm, Portfolio
    algo = QCAlgorithm()
    algo.time = datetime.now()
    algo.portfolio = Portfolio(cash=100_000)
    algo.securities = {}
    return algo


@pytest.fixture
def mock_history():
    """
    Factory fixture: returns a function that generates mock historical data.
    
    Usage:
        history_df = mock_history(symbol="AAPL", n_bars=100)
    """
    def _mock_history(symbol: str = "AAPL", n_bars: int = 100,
                     base_price: float = 150.0):
        """
        Generate deterministic historical DataFrame.
        
        Args:
            symbol: Symbol name
            n_bars: Number of bars
            base_price: Starting price
            
        Returns:
            pd.DataFrame: OHLCV data
        """
        dates = pd.date_range(end=datetime.now(), periods=n_bars, freq="D")
        closes = [base_price + i * 0.5 for i in range(n_bars)]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        opens = closes
        volumes = [1_000_000] * n_bars
        
        return pd.DataFrame({
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }, index=dates)
    
    return _mock_history


@pytest.fixture
def mock_trade_record():
    """
    Factory fixture: create a single-leg open Trade via PositionManager.add_leg.

    Usage:
        trade = mock_trade_record(symbol="AAPL", entry_price=150.0, quantity=10)
    """
    def _mock_trade(symbol: str = "AAPL", entry_price: float = 150.0,
                   quantity: int = 10, entry_date=None, algorithm=None):
        from handlers.position_manager import PositionManager
        from type_stubs import QCAlgorithm
        if algorithm is None:
            algorithm = QCAlgorithm()
        if entry_date is None:
            entry_date = datetime.now().date()
        pm = PositionManager(algorithm)
        return pm.add_leg(symbol, entry_price, quantity, entry_date)

    return _mock_trade


@pytest.fixture
def mock_instrument():
    """
    Factory fixture: create a mock instrument (option contract).
    
    Usage:
        instr = mock_instrument(symbol="AAPL_C_150_20250117", dte=14, delta=0.20)
    """
    def _mock_instr(symbol: str = "AAPL_C_150_20250117", dte: int = 14,
                   price: float = 5.50, delta: float = 0.20,
                   bid: float = 5.45, ask: float = 5.55,
                   open_interest: int = 500):
        return type("Instrument", (), {
            "symbol": symbol,
            "dte": dte,
            "price": price,
            "delta": delta,
            "bid": bid,
            "ask": ask,
            "open_interest": open_interest,
        })()
    
    return _mock_instr


@pytest.fixture
def mock_indicators():
    """
    Factory fixture: create a mock indicator dict.
    
    Usage:
        indicators = mock_indicators(price=155.0, sma_50=150.0, ema_21=151.0, atr_14=2.5)
    """
    def _mock_ind(price: float = 155.0,
                 sma_50: float = 150.0, ema_8: float = 154.0,
                 ema_21: float = 153.0, ema_34: float = 151.5,
                 atr_14: float = 2.5, atr_mean: float = 2.3):
        return {
            "price": price,
            "sma_50": sma_50,
            "ema_8": ema_8,
            "ema_21": ema_21,
            "ema_34": ema_34,
            "atr_14": atr_14,
            "atr_mean": atr_mean,
        }

    return _mock_ind


@pytest.fixture
def mock_option_contract():
    """
    Factory fixture: create a mock OptionContract.

    Usage:
        contract = mock_option_contract(strike=160.0, delta=0.20, dte=14)
    """
    def _mock_contract(symbol: str = "AAPL_C_160_20260320",
                       underlying: str = "AAPL",
                       strike: float = 160.0,
                       expiry_offset_days: int = 14,
                       right: str = "Call",
                       delta: float = 0.20,
                       bid: float = 2.45, ask: float = 2.55,
                       open_interest: int = 1500,
                       last_price: float = 2.50):
        from type_stubs import OptionContract
        expiry = datetime.now() + timedelta(days=expiry_offset_days)
        return OptionContract(
            symbol=symbol,
            underlying_symbol=underlying,
            strike=strike,
            expiry=expiry,
            right=right,
            delta=delta,
            bid=bid,
            ask=ask,
            open_interest=open_interest,
            last_price=last_price,
        )

    return _mock_contract


# ============================================================================
# MEMORY INVESTIGATION FIXTURES
# ============================================================================

@pytest.fixture
def memory_snapshot():
    """
    tracemalloc snapshot helper for memory-leak longevity tests.

    Usage:
        def test_something(memory_snapshot):
            memory_snapshot.start()
            # ... run code under test ...
            diff = memory_snapshot.diff()   # list of StatisticDiff, desc order
            total_added = memory_snapshot.bytes_added()

    Automatically stops tracemalloc after the test regardless of outcome.
    """
    import tracemalloc

    class _Snapshot:
        def __init__(self):
            self._before = None

        def start(self):
            tracemalloc.start()
            self._before = tracemalloc.take_snapshot()

        def diff(self):
            after = tracemalloc.take_snapshot()
            return after.compare_to(self._before, "lineno")

        def bytes_added(self) -> int:
            return sum(s.size_diff for s in self.diff() if s.size_diff > 0)

    snap = _Snapshot()
    yield snap
    tracemalloc.stop()
