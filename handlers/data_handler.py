"""
handlers/data_handler.py — Indicator Computation & Caching

Computes per-(symbol, date):
  close, open, low, prior_close, prior_low,
  EMA21, SMA50, prior_EMA21, prior_SMA50,
  dollar_volume_20d, atr_14, atr_stretch_low, is_blue_bar

Cache key: (str(symbol), algo.time.date()).
Test injection: callers may pass `history=` to bypass the LEAN history API.
"""

from typing import Optional

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
        if indicators is not None and history is None:
            self._cache[cache_key] = indicators
        return indicators

    # ------------------------------------------------------------------
    def _fetch_history(self, symbol):
        try:
            from AlgorithmImports import Resolution  # type: ignore
            return self._algo.history(symbol, self._lookback, Resolution.DAILY)
        except Exception:
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
        ) + 1
        if n < min_required:
            return None

        close = float(closes[-1])
        open_ = float(opens[-1])
        low = float(lows[-1])
        prior_close = float(closes[-2])
        prior_low = float(lows[-2])

        ema_period = config.STOCK_EMA_PERIOD  # 21 == REGIME_EMA_PERIOD
        sma_period = config.STOCK_SMA_PERIOD  # 50 == REGIME_SMA_PERIOD

        ema_today = self._ema(closes, ema_period)
        ema_prior = self._ema(closes[:-1], ema_period)
        sma_today = sum(closes[-sma_period:]) / sma_period
        sma_prior = sum(closes[-sma_period - 1:-1]) / sma_period

        atr_14 = self._atr(highs, lows, closes, config.ATR_PERIOD)
        atr_stretch_low = (low - ema_today) / atr_14 if atr_14 > 0 else 0.0
        is_blue_bar = close >= open_

        dv_lookback = config.DOLLAR_VOLUME_LOOKBACK
        dollar_volume_20d = sum(
            float(closes[i]) * float(volumes[i]) for i in range(-dv_lookback, 0)
        ) / dv_lookback

        return {
            "close": close,
            "open": open_,
            "low": low,
            "prior_close": prior_close,
            "prior_low": prior_low,
            "EMA21": ema_today,
            "SMA50": sma_today,
            "prior_EMA21": ema_prior,
            "prior_SMA50": sma_prior,
            "dollar_volume_20d": dollar_volume_20d,
            "atr_14": atr_14,
            "atr_stretch_low": atr_stretch_low,
            "is_blue_bar": is_blue_bar,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _ema(values, period: int) -> float:
        """Standard EMA seeded from SMA of first `period` closes."""
        if len(values) < period:
            return float("nan")
        seed = sum(values[:period]) / period
        alpha = 2.0 / (period + 1)
        ema = seed
        for v in values[period:]:
            ema = alpha * float(v) + (1 - alpha) * ema
        return float(ema)

    @staticmethod
    def _atr(highs, lows, closes, period: int) -> float:
        n = len(closes)
        if n < period + 1:
            return 0.0
        trs = []
        for i in range(n - period, n):
            hi, lo, prev_close = float(highs[i]), float(lows[i]), float(closes[i - 1])
            tr = max(hi - lo, abs(hi - prev_close), abs(lo - prev_close))
            trs.append(tr)
        return sum(trs) / period

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
