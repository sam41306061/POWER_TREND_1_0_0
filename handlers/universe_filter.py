"""
handlers/universe_filter.py — Dynamic Universe Selector

Responsibility:
  Provide a QC coarse-fundamental selection callback that:
    1. Filters by liquidity floor (price >= MIN_PRICE, dollar_volume >= MIN_DOLLAR_VOLUME)
    2. Ranks survivors by 20-day average dollar volume (uses fundamental's dollar_volume)
    3. Selects the top UNIVERSE_TOP_N
    4. Force-includes REGIME_SYMBOL (QQQ)
    5. Caches the resulting symbol set for UNIVERSE_REFRESH_DAYS

Pure-Python; no LEAN imports. Coarse rows are duck-typed
(`.symbol`, `.price`, `.dollar_volume`).
"""

from datetime import date
from typing import Iterable, Optional

import config


class DynamicUniverseSelector:
    """Coarse-fundamental selector with cadence cache + QQQ force-include."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._cached_symbols: list = []
        self._last_refresh: Optional[date] = None

    def select_coarse(self, coarse: Iterable) -> list:
        """QC coarse callback: list[Coarse] -> list[Symbol]."""
        today = self._algo.time.date()

        if self._should_use_cache(today):
            return self._cached_symbols

        coarse_list = list(coarse)
        filtered = [
            c for c in coarse_list
            if getattr(c, "price", 0) >= config.MIN_PRICE
            and getattr(c, "dollar_volume", 0) >= config.MIN_DOLLAR_VOLUME
            and getattr(c, "has_fundamental_data", True)
        ]
        filtered.sort(key=lambda c: c.dollar_volume, reverse=True)
        top = filtered[: config.UNIVERSE_TOP_N]

        symbols = [c.symbol for c in top]
        symbols = self._force_include_regime(symbols, coarse_list)

        self._cached_symbols = symbols
        self._last_refresh = today
        self._algo.debug(
            f"[UNIVERSE] {today}: selected {len(symbols)} symbols (top {config.UNIVERSE_TOP_N})"
        )
        return symbols

    def _should_use_cache(self, today: date) -> bool:
        if self._last_refresh is None or not self._cached_symbols:
            return False
        return (today - self._last_refresh).days < config.UNIVERSE_REFRESH_DAYS

    def _force_include_regime(self, symbols: list, coarse_list: list) -> list:
        regime_str = config.REGIME_SYMBOL
        if any(str(s).split()[0].upper() == regime_str for s in symbols):
            return symbols
        for c in coarse_list:
            if str(c.symbol).split()[0].upper() == regime_str:
                return symbols + [c.symbol]
        return symbols

    @property
    def active_symbols(self) -> list:
        return list(self._cached_symbols)
