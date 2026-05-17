"""
handlers/data_handler.py — Indicator Computation & Caching

Computes per-(symbol, date):
  close, open, high, low, prior_close, prior_low,
  EMA21, SMA50, SMA10, prior_EMA21, prior_SMA50,
  dollar_volume_20d, atr_14, atr_50,
  atr_stretch_low, high_vs_ema21, high_vs_sma10, is_blue_bar

Cache key: (str(symbol), algo.time.date()).
Test injection: callers may pass `history=` to bypass the LEAN history API.
"""

from typing import Optional

import numpy as np

import config


class DataHandler:
    """Compute and cache daily technical indicators per symbol."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._cache: dict[tuple, dict] = {}
        # EMA-seed lookback: enough bars to seed EMA21 from SMA + warmup
        self._lookback = max(
            config.STOCK_SMA_PERIOD,
            config.REGIME_SMA_PERIOD,
            config.DOLLAR_VOLUME_LOOKBACK,
            config.ATR_PERIOD,
            config.WEBBY_RSI_ATR_PERIOD,
        ) + 30

    def clear_cache(self) -> None:
        self._cache.clear()

    def get_indicators(self, symbol, history=None) -> Optional[dict]:
        sym_str = str(symbol)
        today = self._algo.time.date()
        cache_key = (sym_str, today)

        if history is None and cache_key in self._cache:
            return self._cache[cache_key]

        bars = history if history is not None else self._fetch_history(symbol)
        indicators = self._compute(bars)
        if indicators is None and bars is not None:
            n = len(bars) if hasattr(bars, "__len__") else "?"
            self._algo.debug(f"[DATA WARN] insufficient bars for {sym_str} ({n} bars) — indicators not computed")
        if indicators is not None and history is None:
            self._cache[cache_key] = indicators
        return indicators

    # ------------------------------------------------------------------
    def _fetch_history(self, symbol):
        try:
            from AlgorithmImports import Resolution  # type: ignore
            return self._algo.history(symbol, self._lookback, Resolution.DAILY)
        except Exception as e:
            self._algo.log(f"[DATA CRITICAL] history fetch failed for {symbol}: {e}")
            return None

    def _compute(self, bars) -> Optional[dict]:
        if bars is None:
            return None

        opens = self._extract(bars, "open")
        highs = self._extract(bars, "high")
        lows = self._extract(bars, "low")
        closes = self._extract(bars, "close")
        volumes = self._extract(bars, "volume")

        n = len(closes)
        min_required = max(
            config.STOCK_SMA_PERIOD,
            config.REGIME_SMA_PERIOD,
            config.DOLLAR_VOLUME_LOOKBACK,
            config.ATR_PERIOD,
            config.WEBBY_RSI_ATR_PERIOD,
        ) + 1
        if n < min_required:
            return None

        close = float(closes[-1])
        open_ = float(opens[-1])
        high = float(highs[-1])
        low = float(lows[-1])
        prior_close = float(closes[-2])
        prior_low = float(lows[-2])

        ema_period = config.STOCK_EMA_PERIOD  # 21 == REGIME_EMA_PERIOD
        sma_period = config.STOCK_SMA_PERIOD  # 50 == REGIME_SMA_PERIOD

        ema_today = self._ema(closes, ema_period)
        ema_prior = self._ema(closes[:-1], ema_period)
        sma_today = sum(closes[-sma_period:]) / sma_period
        sma_prior = sum(closes[-sma_period - 1:-1]) / sma_period
        sma10 = sum(closes[-config.STOCK_SMA10_PERIOD:]) / config.STOCK_SMA10_PERIOD

        atr_14 = self._atr(highs, lows, closes, config.ATR_PERIOD)
        atr_50 = self._atr(highs, lows, closes, config.WEBBY_RSI_ATR_PERIOD)
        atr_stretch_low = (low - ema_today) / atr_50 if atr_50 > 0 else 0.0
        high_vs_ema21 = (ema_today - high) / atr_50 if atr_50 > 0 else 0.0
        high_vs_sma10 = (high - sma10) / atr_50 if atr_50 > 0 else 0.0
        is_blue_bar = close >= open_

        dv_lookback = config.DOLLAR_VOLUME_LOOKBACK
        dollar_volume_20d = sum(
            float(closes[i]) * float(volumes[i]) for i in range(-dv_lookback, 0)
        ) / dv_lookback

        return {
            "close": close,
            "open": open_,
            "high": high,
            "low": low,
            "prior_close": prior_close,
            "prior_low": prior_low,
            "EMA21": ema_today,
            "SMA50": sma_today,
            "SMA10": sma10,
            "prior_EMA21": ema_prior,
            "prior_SMA50": sma_prior,
            "dollar_volume_20d": dollar_volume_20d,
            "atr_14": atr_14,
            "atr_50": atr_50,
            "atr_stretch_low": atr_stretch_low,
            "high_vs_ema21": high_vs_ema21,
            "high_vs_sma10": high_vs_sma10,
            "is_blue_bar": is_blue_bar,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _ema(values, period: int) -> float:
        """Standard EMA seeded from SMA of first `period` closes. NumPy-backed seed."""
        arr = np.asarray(values, dtype=np.float64)
        n = len(arr)
        if n < period:
            return float("nan")
        alpha = 2.0 / (period + 1)
        ema = float(np.mean(arr[:period]))
        for v in arr[period:]:
            ema = alpha * v + (1.0 - alpha) * ema
        return ema

    @staticmethod
    def _atr(highs, lows, closes, period: int) -> float:
        n = len(closes)
        if n < period + 1:
            return 0.0
        hi = np.asarray(highs[-(period + 1):], dtype=np.float64)
        lo = np.asarray(lows[-(period + 1):], dtype=np.float64)
        pc = np.asarray(closes[-(period + 1):], dtype=np.float64)
        tr = np.maximum(hi[1:] - lo[1:], np.maximum(np.abs(hi[1:] - pc[:-1]), np.abs(lo[1:] - pc[:-1])))
        return float(np.mean(tr))

    @staticmethod
    def _extract(bars, column: str) -> list:
        """Support DataFrame-like (LEAN history) and lists of bar objects (test stubs)."""
        if hasattr(bars, "columns") and column in getattr(bars, "columns", []):
            return list(bars[column].values)
        if hasattr(bars, "__getitem__") and not isinstance(bars, list):
            try:
                return list(bars[column].values)
            except Exception:
                pass
        # list of bar-like objects
        return [float(getattr(b, column)) for b in bars]
