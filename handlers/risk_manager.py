"""
handlers/risk_manager.py — Account-Level Risk Guards

Tracks portfolio high-water mark (HWM) and enforces the
MAX_ACCOUNT_DRAWDOWN_PCT entry gate.

If the current portfolio value sits more than MAX_ACCOUNT_DRAWDOWN_PCT
below the HWM, all NEW entries (initial + add-on) are blocked. Existing
positions continue to be managed by the exit engine — risk only gates new
exposure.

Call `update()` once per day at the top of _evaluate().
"""

from __future__ import annotations

import config


class RiskManager:
    """Account HWM + drawdown entry gate."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self._hwm: float = float(algorithm.portfolio.total_portfolio_value)

    # ------------------------------------------------------------------
    # Daily update
    # ------------------------------------------------------------------
    def update(self) -> None:
        equity = float(self._algo.portfolio.total_portfolio_value)
        if equity > self._hwm:
            self._hwm = equity

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    @property
    def hwm(self) -> float:
        return self._hwm

    @property
    def current_drawdown(self) -> float:
        """Drawdown as positive fraction (e.g. 0.12 == 12% below HWM)."""
        if self._hwm <= 0:
            return 0.0
        equity = float(self._algo.portfolio.total_portfolio_value)
        return max(0.0, 1.0 - equity / self._hwm)

    def is_new_entry_allowed(self) -> bool:
        """Block new entries when drawdown breaches threshold."""
        return self.current_drawdown < config.MAX_ACCOUNT_DRAWDOWN_PCT
