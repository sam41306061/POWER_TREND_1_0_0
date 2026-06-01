"""DataHandler indicator computation tests."""

import numpy as np
import pandas as pd

import config
from handlers.data_handler import DataHandler


def _make_history(n_bars: int = 120, base: float = 100.0) -> pd.DataFrame:
    """Build a deterministic upward-trending OHLCV DataFrame."""
    closes = np.array([base + i * 0.5 for i in range(n_bars)], dtype=float)
    opens = closes - 0.25
    highs = closes + 0.6
    lows = closes - 0.6
    volumes = np.full(n_bars, 1_000_000.0)
    idx = pd.date_range(end="2024-01-01", periods=n_bars, freq="D")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=idx,
    )


def test_returns_none_for_insufficient_history(mock_algorithm):
    mock_algorithm.history = lambda *a, **k: pd.DataFrame()
    dh = DataHandler(mock_algorithm)
    assert dh.get_indicators("AAPL") is None


def test_indicator_dict_has_required_keys(mock_algorithm):
    df = _make_history()
    mock_algorithm.history = lambda *a, **k: df
    dh = DataHandler(mock_algorithm)
    ind = dh.get_indicators("AAPL")
    assert ind is not None
    required = {
        "close", "open", "high", "low", "prior_close", "prior_low",
        "ema21", "sma50", "sma10", "prior_ema21", "prior_sma50",
        "sma50_n_days_ago", "dollar_volume_20d", "atr14", "atr50",
        "atr_stretch_low", "high_vs_ema21", "high_vs_sma10", "is_blue_bar",
    }
    assert required.issubset(ind.keys())


def test_cache_returns_same_object(mock_algorithm):
    df = _make_history()
    mock_algorithm.history = lambda *a, **k: df
    dh = DataHandler(mock_algorithm)
    a = dh.get_indicators("AAPL")
    b = dh.get_indicators("AAPL")
    assert a is b


def test_clear_cache_recomputes(mock_algorithm):
    df = _make_history()
    mock_algorithm.history = lambda *a, **k: df
    dh = DataHandler(mock_algorithm)
    a = dh.get_indicators("AAPL")
    dh.clear_cache()
    b = dh.get_indicators("AAPL")
    assert a is not b


def test_blue_bar_flag(mock_algorithm):
    df = _make_history()
    # Force last bar red
    df.iloc[-1, df.columns.get_loc("open")] = df.iloc[-1]["close"] + 1.0
    mock_algorithm.history = lambda *a, **k: df
    dh = DataHandler(mock_algorithm)
    ind = dh.get_indicators("AAPL")
    assert ind["is_blue_bar"] is False
