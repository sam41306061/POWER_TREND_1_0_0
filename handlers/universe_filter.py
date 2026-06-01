"""
handlers/universe_filter.py — Dynamic Universe Selection

Selects the top-N most liquid US equities by 20-day average dollar volume,
refreshed every UNIVERSE_REFRESH_DAYS days. The regime symbol (QQQ) is
always force-included so the regime filter can run regardless of cache state.

Plugs into QC via `algo.add_universe(filter.coarse_filter)` (CoarseFundamental
callback). Selection cache reduces CPU on non-refresh days.

Contract:
    coarse_filter(coarse) → list[Symbol]   QC universe selection callback
    is_in_universe(symbol) → bool
    current_universe → list[Symbol]        Snapshot of last selection
"""

from __future__ import annotations

from datetime import date, timedelta

import config


class DynamicUniverseSelector:
    """Top-N by 20d dollar volume with 14-day refresh cache."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._cached_universe: list = []      # list[Symbol]
        self._last_refresh_date: date | None = None
        # Symbols force-kept in the universe because we still hold a position.
        # Prevents QC's default "remove from universe = liquidate" path from
        # bypassing ExitEngine. Caller (main.on_securities_changed) populates
        # this; ExitEngine releases via release_symbol() when fully closed.
        self._retained: set = set()

    # ------------------------------------------------------------------
    # QC callback
    # ------------------------------------------------------------------
    def coarse_filter(self, coarse):
        """
        QC coarse-universe callback.

        Args:
            coarse: iterable of CoarseFundamental objects with
                .symbol, .price, .dollar_volume, .has_fundamental_data

        Returns:
            list[Symbol]
        """
        today = self._algo.time.date()
        if self._should_use_cache(today):
            return self._cached_universe

        # Liquidity filter: tradable, priced above floor, sufficient $-volume
        filtered = [
            c for c in coarse
            if c.has_fundamental_data
            and c.price >= config.MIN_PRICE
            and c.dollar_volume >= config.MIN_DOLLAR_VOLUME
        ]

        # Top-N by dollar volume (already 20d average in QC coarse data)
        top = sorted(filtered, key=lambda c: c.dollar_volume, reverse=True)[
            : config.UNIVERSE_TOP_N
        ]
        symbols = [c.symbol for c in top]

        # Force-include regime symbol
        regime_sym = self._regime_symbol()
        if regime_sym is not None and regime_sym not in symbols:
            symbols.append(regime_sym)

        # Force-include any symbol we still hold a position in.
        for sym in self._retained:
            if sym not in symbols:
                symbols.append(sym)

        self._cached_universe = symbols
        self._last_refresh_date = today
        self._algo.debug(
            f"[UNIVERSE] Refreshed: {len(symbols)} symbols on {today.isoformat()}"
        )
        return symbols

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    @property
    def current_universe(self) -> list:
        return list(self._cached_universe)

    def is_in_universe(self, symbol) -> bool:
        return symbol in self._cached_universe

    def retain_symbol(self, symbol) -> None:
        """Keep ``symbol`` in the universe across refreshes (used while a
        position is still open). Idempotent."""
        self._retained.add(symbol)
        if symbol not in self._cached_universe:
            self._cached_universe.append(symbol)

    def release_symbol(self, symbol) -> None:
        """Stop force-retaining ``symbol`` (called once the position closes).
        Symbol will drop out at the next refresh if it no longer qualifies."""
        self._retained.discard(symbol)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _should_use_cache(self, today: date) -> bool:
        if self._last_refresh_date is None or not self._cached_universe:
            return False
        return (today - self._last_refresh_date) < timedelta(
            days=config.UNIVERSE_REFRESH_DAYS
        )

    def _regime_symbol(self):
        """Return the regime Symbol object if QC has registered it, else None."""
        for sym in self._algo.securities:
            if str(sym).upper().startswith(config.REGIME_SYMBOL.upper()):
                return sym
        return None
