"""tests/unit/test_data_handler.py — DataHandler indicator computation."""

from datetime import date, timedelta

import pandas as pd

from handlers.data_handler import DataHandler, _sma, _ema_series, _atr


def _build_history(n: int = 120, start_price: float = 100.0):
    """Build a deterministic upward-drifting OHLCV DataFrame."""
    dates = pd.date_range(end=date(2025, 6, 1), periods=n, freq="D")
    closes = [start_price + i * 0.5 for i in range(n)]
    opens = [c - 0.25 for c in closes]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    volumes = [1_000_000] * n
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    )


class TestDataHandlerCache:
    def test_clear_cache_empties(self, mock_algorithm):
        h = DataHandler(mock_algorithm)
        h._cache[("AAPL", date(2025, 1, 1))] = {"x": 1}
        h.clear_cache()
        assert h._cache == {}

    def test_get_indicators_returns_none_when_no_history(self, mock_algorithm):
        h = DataHandler(mock_algorithm)
        assert h.get_indicators("AAPL") is None


class TestDataHandlerCompute:
    def _make(self, mock_algorithm, n=120):
        df = _build_history(n=n)
        mock_algorithm.history = lambda *_args, **_kw: df
        return DataHandler(mock_algorithm), df

    def test_returns_18_fields(self, mock_algorithm):
        h, _ = self._make(mock_algorithm)
        ind = h.get_indicators("AAPL")
        expected = {
            "open", "high", "low", "close",
            "prior_close", "prior_low", "prior_EMA21", "prior_SMA50",
            "EMA21", "SMA50", "SMA10",
            "atr_14", "atr_50", "dollar_volume_20d",
            "atr_stretch_low", "high_vs_ema21", "high_vs_sma10",
            "is_blue_bar",
        }
        assert set(ind.keys()) == expected

    def test_webby_rsi_formulas(self, mock_algorithm):
        h, _ = self._make(mock_algorithm)
        ind = h.get_indicators("AAPL")
        expected_stretch = (ind["low"] - ind["EMA21"]) / ind["atr_50"]
        expected_high_vs_ema21 = (ind["EMA21"] - ind["high"]) / ind["atr_50"]
        expected_high_vs_sma10 = (ind["high"] - ind["SMA10"]) / ind["atr_50"]
        assert ind["atr_stretch_low"] == expected_stretch
        assert ind["high_vs_ema21"] == expected_high_vs_ema21
        assert ind["high_vs_sma10"] == expected_high_vs_sma10

    def test_blue_bar_when_close_ge_open(self, mock_algorithm):
        h, _ = self._make(mock_algorithm)
        ind = h.get_indicators("AAPL")
        assert ind["is_blue_bar"] is True

    def test_returns_none_when_history_too_short(self, mock_algorithm):
        h, _ = self._make(mock_algorithm, n=20)
        assert h.get_indicators("AAPL") is None

    def test_cache_hits_on_second_call(self, mock_algorithm):
        h, _ = self._make(mock_algorithm)
        a = h.get_indicators("AAPL")
        b = h.get_indicators("AAPL")
        assert a is b  # same dict object — cache hit


class TestPureHelpers:
    def test_sma_basic(self):
        assert _sma([1, 2, 3, 4, 5], 3) == 4.0
        assert _sma([1, 2, 3, 4, 5], 3, offset=1) == 3.0

    def test_ema_series_seed_equals_sma(self):
        vals = [float(i) for i in range(1, 31)]
        ema = _ema_series(vals, 5)
        assert ema[4] == sum(vals[:5]) / 5  # seed bar

    def test_atr_constant_range(self):
        # Constant range of exactly 1.0 → ATR == 1.0 regardless of period.
        n = 30
        highs = [10.0 + 0.5] * n
        lows = [10.0 - 0.5] * n
        closes = [10.0] * n
        assert abs(_atr(highs, lows, closes, 14) - 1.0) < 1e-9
