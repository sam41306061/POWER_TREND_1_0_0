"""
handlers/data_handler.py — Indicator Computation & Caching

Computes per-symbol per-day indicator dicts used by the regime filter,
entry engine, exit engine, and pyramiding manager.

All values for a (symbol, date) key are computed once and cached. Call
clear_cache() at the top of each daily _evaluate() pass.

Returned dict keys (per symbol, per date):

    close, open, high, low                    # OHLC today
    prior_close, prior_low                    # OHLC yesterday
    ema21, sma50, sma10                       # Current MAs (close)
    prior_ema21, prior_sma50                  # Yesterday's EMA21/SMA50
    sma50_n_days_ago                          # SMA50 today vs SMA_SLOPE_LOOKBACK days ago
    dollar_volume_20d                         # 20d avg $-volume
    atr14, atr50                              # ATR(14) for stops, ATR(50) for stretch
    atr_stretch_low                           # (low - ema21) / atr50
    high_vs_ema21                             # (ema21 - high) / atr50  (negative = above)
    high_vs_sma10                             # (high - sma10) / atr50
    is_blue_bar                               # close >= open

Returns None when history is insufficient.
"""

from __future__ import annotations

import numpy as np

import config


# Minimum bars needed: largest lookback + buffer
_MIN_HISTORY = (
    max(
        config.STOCK_SMA_PERIOD,
        config.WEBBY_RSI_ATR_PERIOD,
        config.DOLLAR_VOLUME_LOOKBACK,
        config.SMA_SLOPE_LOOKBACK + config.STOCK_SMA_PERIOD,
    )
    + 5
)


class DataHandler:
    """Compute and cache technical indicators per (symbol, date)."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._cache: dict[tuple, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def clear_cache(self) -> None:
        self._cache.clear()

    def get_indicators(self, symbol) -> dict | None:
        sym_key = str(symbol)
        today = self._algo.time.date()
        cache_key = (sym_key, today)

        if cache_key in self._cache:
            return self._cache[cache_key]

        ind = self._compute_indicators(symbol)
        if ind is not None:
            self._cache[cache_key] = ind
        return ind

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------
    def _compute_indicators(self, symbol) -> dict | None:
        try:
            from AlgorithmImports import Resolution
        except ImportError:  # local test path
            Resolution = type("Resolution", (), {"DAILY": "daily"})

        bars = self._algo.history(symbol, _MIN_HISTORY, Resolution.DAILY)
        if bars is None or len(bars) < _MIN_HISTORY:
            return None

        # Accept either a pandas DataFrame (QC) or a list of TradeBar (stubs).
        opens, highs, lows, closes, volumes = self._extract_ohlcv(bars)
        if closes is None or len(closes) < _MIN_HISTORY:
            return None

        n = len(closes)

        # MAs on closes
        ema21 = _ema(closes, config.STOCK_EMA_PERIOD)
        sma50 = _sma(closes, config.STOCK_SMA_PERIOD)
        sma10 = _sma(closes, config.STOCK_SMA10_PERIOD)

        # Need yesterday's MAs as well
        ema21_prev = _ema(closes[:-1], config.STOCK_EMA_PERIOD)
        sma50_prev = _sma(closes[:-1], config.STOCK_SMA_PERIOD)

        # SMA50 N days ago (for rising-slope check)
        lookback = config.SMA_SLOPE_LOOKBACK
        if n - lookback < config.STOCK_SMA_PERIOD:
            return None
        sma50_n_ago = _sma(closes[: n - lookback], config.STOCK_SMA_PERIOD)

        # ATR
        atr14 = _atr(highs, lows, closes, config.ATR_PERIOD)
        atr50 = _atr(highs, lows, closes, config.WEBBY_RSI_ATR_PERIOD)
        if atr14 is None or atr50 is None or atr50 <= 0:
            return None

        # Dollar volume (20d avg)
        dv_lookback = config.DOLLAR_VOLUME_LOOKBACK
        dollar_vol_20d = float(
            np.mean(closes[-dv_lookback:] * volumes[-dv_lookback:])
        )

        close = float(closes[-1])
        open_ = float(opens[-1])
        high = float(highs[-1])
        low = float(lows[-1])
        prior_close = float(closes[-2])
        prior_low = float(lows[-2])

        atr_stretch_low = (low - ema21) / atr50
        high_vs_ema21 = (ema21 - high) / atr50
        high_vs_sma10 = (high - sma10) / atr50

        return {
            "close": close,
            "open": open_,
            "high": high,
            "low": low,
            "prior_close": prior_close,
            "prior_low": prior_low,
            "ema21": float(ema21),
            "sma50": float(sma50),
            "sma10": float(sma10),
            "prior_ema21": float(ema21_prev),
            "prior_sma50": float(sma50_prev),
            "sma50_n_days_ago": float(sma50_n_ago),
            "dollar_volume_20d": dollar_vol_20d,
            "atr14": float(atr14),
            "atr50": float(atr50),
            "atr_stretch_low": float(atr_stretch_low),
            "high_vs_ema21": float(high_vs_ema21),
            "high_vs_sma10": float(high_vs_sma10),
            "is_blue_bar": bool(close >= open_),
        }

    # ------------------------------------------------------------------
    # OHLCV extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_ohlcv(bars):
        # pandas DataFrame path (QC live/backtest)
        try:
            cols = bars.columns
            if hasattr(bars, "columns") and "close" in cols:
                opens = bars["open"].to_numpy(dtype=float)
                highs = bars["high"].to_numpy(dtype=float)
                lows = bars["low"].to_numpy(dtype=float)
                closes = bars["close"].to_numpy(dtype=float)
                volumes = bars["volume"].to_numpy(dtype=float)
                return opens, highs, lows, closes, volumes
        except Exception:
            pass

        # Iterable of TradeBar (test stubs)
        try:
            opens = np.array([b.open for b in bars], dtype=float)
            highs = np.array([b.high for b in bars], dtype=float)
            lows = np.array([b.low for b in bars], dtype=float)
            closes = np.array([b.close for b in bars], dtype=float)
            volumes = np.array([b.volume for b in bars], dtype=float)
            return opens, highs, lows, closes, volumes
        except Exception:
            return None, None, None, None, None


# ----------------------------------------------------------------------
# Indicator primitives (NumPy)
# ----------------------------------------------------------------------


def _sma(values, period: int) -> float | None:
    if len(values) < period:
        return None
    return float(np.mean(values[-period:]))


def _ema(values, period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1)
    # Seed EMA with SMA of first `period` values, then recurse
    ema = float(np.mean(values[:period]))
    for v in values[period:]:
        ema = alpha * float(v) + (1 - alpha) * ema
    return ema


def _atr(highs, lows, closes, period: int) -> float | None:
    if len(closes) < period + 1:
        return None
    tr = np.maximum.reduce(
        [
            highs[1:] - lows[1:],
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:] - closes[:-1]),
        ]
    )
    # Wilder smoothing: average first `period` TRs, then EMA-style recursion
    atr = float(np.mean(tr[:period]))
    for t in tr[period:]:
        atr = (atr * (period - 1) + float(t)) / period
    return atr
