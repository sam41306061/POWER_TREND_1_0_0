"""
handlers/data_handler.py — Indicator Computation & Caching

Responsibility:
  Compute and cache technical indicators (SMA, EMA, ATR, etc.) per symbol per day.
  Cache key: (symbol, date) — invalidated at the start of each daily scan.

Contract:
  get_indicators(symbol) → dict   Indicator values for the symbol
  clear_cache()                    Reset cache for new scan cycle
"""

import config


class DataHandler:
    """Compute and cache technical indicators."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._cache: dict[tuple, dict] = {}  # {(symbol_str, date): indicator_dict}

    def clear_cache(self) -> None:
        """Clear the indicator cache. Call at the start of each daily scan."""
        self._cache.clear()

    def get_indicators(self, symbol) -> dict | None:
        """
        Compute or return cached indicators for the given symbol.

        Args:
            symbol: Equity Symbol object

        Returns:
            dict with indicator values, or None if data is insufficient.

            Expected keys (customize to your strategy):
            {
                "price":      float,  # latest close
                "sma_long":   float,  # SMA over SMA_LONG_PERIOD
                "ema_short":  float,  # EMA over EMA_SHORT_PERIOD
                "ema_mid":    float,  # EMA over EMA_MID_PERIOD
                "ema_long":   float,  # EMA over EMA_LONG_PERIOD
                "atr":        float,  # ATR over ATR_PERIOD
                "atr_mean":   float,  # Rolling mean of ATR
            }
        """
        sym_str = str(symbol)
        today = self._algo.time.date()
        cache_key = (sym_str, today)

        if cache_key in self._cache:
            return self._cache[cache_key]

        indicators = self._compute_indicators(symbol)
        if indicators is not None:
            self._cache[cache_key] = indicators

        return indicators

    def _compute_indicators(self, symbol) -> dict | None:
        """
        Fetch history and compute indicators.

        TODO: Implement indicator computation using self._algo.history()

        Example:
            bars = self._algo.history(symbol, config.SMA_LONG_PERIOD + 20, Resolution.DAILY)
            if bars is None or len(bars) < config.SMA_LONG_PERIOD:
                return None
            closes = bars["close"].values
            return {
                "price": float(closes[-1]),
                "sma_long": float(closes[-config.SMA_LONG_PERIOD:].mean()),
                ...
            }
        """
        return None
