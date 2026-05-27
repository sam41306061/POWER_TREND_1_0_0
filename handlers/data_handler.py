"""
handlers/data_handler.py — Daily indicator computation & per-day cache.

Computes the 18 fields per (symbol, date) required by entry/exit/regime engines:
  OHLC: close, open, high, low
  Prior bar: prior_close, prior_low, prior_EMA21, prior_SMA50
  Moving averages: EMA21, SMA50, SMA10
  Volatility: atr_14, atr_50, dollar_volume_20d
  Webby RSI: atr_stretch_low, high_vs_ema21, high_vs_sma10
  Signal: is_blue_bar (close >= open)

Cache is keyed by (symbol_str, date) and cleared by the caller at the start
of each daily evaluation.
"""

from typing import Optional

import config


# History buffer must cover SMA50, ATR50, and EMA21 seeding plus a small margin.
_HISTORY_BARS = max(
    config.STOCK_SMA_PERIOD,
    config.WEBBY_RSI_ATR_PERIOD,
    config.DOLLAR_VOLUME_LOOKBACK,
) + 30


class DataHandler:
    """Compute and cache per-symbol daily indicators."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._cache: dict[tuple, dict] = {}

    def clear_cache(self) -> None:
        """Reset cache. Call once per daily evaluation."""
        self._cache.clear()

    def get_indicators(self, symbol) -> Optional[dict]:
        """Return cached indicator dict for *symbol*, or None if data is short."""
        sym_str = str(symbol)
        today = self._algo.time.date()
        key = (sym_str, today)
        if key in self._cache:
            return self._cache[key]

        indicators = self._compute_indicators(symbol)
        if indicators is not None:
            self._cache[key] = indicators
        return indicators

    # ------------------------------------------------------------------ #

    def _compute_indicators(self, symbol) -> Optional[dict]:
        try:
            from AlgorithmImports import Resolution  # type: ignore
            resolution = Resolution.DAILY
        except Exception:
            resolution = None

        bars = self._algo.history(symbol, _HISTORY_BARS, resolution)
        if bars is None:
            return None

        try:
            opens = [float(x) for x in bars["open"].values]
            highs = [float(x) for x in bars["high"].values]
            lows = [float(x) for x in bars["low"].values]
            closes = [float(x) for x in bars["close"].values]
            volumes = [float(x) for x in bars["volume"].values]
        except (KeyError, TypeError, AttributeError):
            return None

        n = len(closes)
        min_needed = max(
            config.STOCK_SMA_PERIOD + 1,
            config.WEBBY_RSI_ATR_PERIOD + 1,
            config.DOLLAR_VOLUME_LOOKBACK,
            config.STOCK_EMA_PERIOD * 2,
        )
        if n < min_needed:
            return None

        # ---- Moving averages (today and prior bar) ----
        ema21_series = _ema_series(closes, config.STOCK_EMA_PERIOD)
        sma50_today = _sma(closes, config.STOCK_SMA_PERIOD, offset=0)
        sma50_prior = _sma(closes, config.STOCK_SMA_PERIOD, offset=1)
        sma10_today = _sma(closes, config.STOCK_SMA10_PERIOD, offset=0)
        ema21_today = ema21_series[-1]
        ema21_prior = ema21_series[-2]

        # ---- ATR ----
        atr_14 = _atr(highs, lows, closes, config.ATR_PERIOD)
        atr_50 = _atr(highs, lows, closes, config.WEBBY_RSI_ATR_PERIOD)
        if atr_14 is None or atr_50 is None or atr_50 == 0.0:
            return None

        # ---- Dollar volume (20d) ----
        lookback = config.DOLLAR_VOLUME_LOOKBACK
        dollar_volume_20d = sum(
            closes[i] * volumes[i] for i in range(n - lookback, n)
        ) / lookback

        # ---- Today OHLC + Webby RSI components ----
        today_open = opens[-1]
        today_high = highs[-1]
        today_low = lows[-1]
        today_close = closes[-1]
        prior_close = closes[-2]
        prior_low = lows[-2]

        atr_stretch_low = (today_low - ema21_today) / atr_50
        high_vs_ema21 = (ema21_today - today_high) / atr_50
        high_vs_sma10 = (today_high - sma10_today) / atr_50

        return {
            # OHLC
            "open": today_open,
            "high": today_high,
            "low": today_low,
            "close": today_close,
            # Prior bar
            "prior_close": prior_close,
            "prior_low": prior_low,
            "prior_EMA21": ema21_prior,
            "prior_SMA50": sma50_prior,
            # Moving averages
            "EMA21": ema21_today,
            "SMA50": sma50_today,
            "SMA10": sma10_today,
            # Volatility / liquidity
            "atr_14": atr_14,
            "atr_50": atr_50,
            "dollar_volume_20d": dollar_volume_20d,
            # Webby RSI
            "atr_stretch_low": atr_stretch_low,
            "high_vs_ema21": high_vs_ema21,
            "high_vs_sma10": high_vs_sma10,
            # Signal
            "is_blue_bar": today_close >= today_open,
        }


# ---------------------------------------------------------------------- #
# Pure helpers over plain Python lists.
# ---------------------------------------------------------------------- #


def _sma(values: list, period: int, offset: int = 0) -> float:
    """Simple moving average over the last *period* bars ending at index -1-offset."""
    end = len(values) - offset
    start = end - period
    window = values[start:end]
    return sum(window) / period


def _ema_series(values: list, period: int) -> list:
    """EMA series seeded with the SMA of the first *period* bars."""
    n = len(values)
    out = [0.0] * n
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    alpha = 2.0 / (period + 1.0)
    for i in range(period, n):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    # Pad early entries so indexing is safe (callers only read the tail).
    for i in range(period - 1):
        out[i] = seed
    return out


def _atr(highs: list, lows: list, closes: list, period: int) -> Optional[float]:
    """Wilder ATR over *period* bars, returning today's value."""
    n = len(closes)
    if n < period + 1:
        return None
    trs = []
    for i in range(1, n):
        hi = highs[i]
        lo = lows[i]
        prev_close = closes[i - 1]
        tr = max(hi - lo, abs(hi - prev_close), abs(lo - prev_close))
        trs.append(tr)
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr
