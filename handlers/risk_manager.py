"""
handlers/risk_manager.py — Account-level drawdown gate.

Tracks the high-water mark of total portfolio equity. When current equity is
drawn down ≥ MAX_ACCOUNT_DRAWDOWN_PCT below HWM, new entries (including
pyramid adds) are suspended. Existing positions are NOT force-closed — the
per-stock exit_engine handles those independently.
"""

import config


class RiskManager:
    """High-water-mark drawdown tracker gating new entries."""

    def __init__(self, algorithm):
        self._algo = algorithm
        self.high_water_mark: float = 0.0
        self.current_equity: float = 0.0

    def update(self, equity: float) -> None:
        """Record the latest equity reading and bump HWM if exceeded."""
        if equity <= 0:
            return
        self.current_equity = equity
        if equity > self.high_water_mark:
            self.high_water_mark = equity

    @property
    def drawdown(self) -> float:
        """Current drawdown as a positive fraction (e.g., 0.12 = down 12%)."""
        if self.high_water_mark <= 0:
            return 0.0
        return max(0.0, 1.0 - (self.current_equity / self.high_water_mark))

    def is_new_entry_allowed(self) -> bool:
        """False once drawdown crosses MAX_ACCOUNT_DRAWDOWN_PCT."""
        return self.drawdown < config.MAX_ACCOUNT_DRAWDOWN_PCT
