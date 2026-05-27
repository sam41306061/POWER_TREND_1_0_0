"""
handlers/universe_filter.py — Dynamic top-N universe by 20d dollar volume.

QuantConnect coarse-filter callback. Selects top `UNIVERSE_TOP_N` US equities
by 20-day average dollar volume, filtered to `price >= MIN_PRICE` and
`20d avg dollar volume >= MIN_DOLLAR_VOLUME`. Refreshes every
`UNIVERSE_REFRESH_DAYS` calendar days; force-includes `REGIME_SYMBOL` (QQQ)
regardless of ranking so the regime filter always has data.

Raw share volume is never consulted as a trading signal — dollar volume only.
"""

from datetime import timedelta
from typing import Optional

import config


class DynamicUniverseSelector:
    """QC coarse-universe selection with 14-day caching and QQQ force-include."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._cached_universe: list = []
        self._last_refresh = None  # datetime.date or None

    # ------------------------------------------------------------------ #

    def coarse_filter(self, coarse) -> list:
        """
        QC coarse-filter callback. *coarse* is an iterable of CoarseFundamental
        objects exposing `.symbol`, `.price`, `.dollar_volume` (today's $-vol),
        and `.has_fundamental_data`.

        Returns a list of Symbol objects (the selected universe), with QQQ
        force-included.
        """
        today = self._algo.time.date()
        if self._cached_universe and self._last_refresh is not None:
            age = (today - self._last_refresh).days
            if age < config.UNIVERSE_REFRESH_DAYS:
                return self._cached_universe

        candidates = []
        for c in coarse:
            try:
                price = float(c.price)
                dvol = float(c.dollar_volume)
            except (AttributeError, TypeError, ValueError):
                continue
            if price < config.MIN_PRICE:
                continue
            if dvol < config.MIN_DOLLAR_VOLUME:
                continue
            if not getattr(c, "has_fundamental_data", True):
                continue
            candidates.append((dvol, c.symbol))

        candidates.sort(key=lambda t: t[0], reverse=True)
        selected_symbols = [sym for _, sym in candidates[: config.UNIVERSE_TOP_N]]

        # Force-include QQQ for regime state machine.
        regime_str = config.REGIME_SYMBOL
        if not any(str(s) == regime_str for s in selected_symbols):
            qqq = self._resolve_regime_symbol(coarse)
            if qqq is not None:
                selected_symbols.append(qqq)

        self._cached_universe = selected_symbols
        self._last_refresh = today
        self._algo.debug(
            f"[UNIVERSE] Refresh on {today}: {len(selected_symbols)} symbols"
        )
        return selected_symbols

    # ------------------------------------------------------------------ #

    def _resolve_regime_symbol(self, coarse) -> Optional[object]:
        """Find QQQ in the coarse list; return its Symbol or None if absent."""
        regime_str = config.REGIME_SYMBOL
        for c in coarse:
            try:
                if str(c.symbol).split()[0].upper() == regime_str:
                    return c.symbol
            except (AttributeError, IndexError):
                continue
        return None
