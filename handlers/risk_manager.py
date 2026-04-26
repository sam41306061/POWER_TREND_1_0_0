"""
handlers/risk_manager.py — Equity tracker (drawdown gate DISABLED).

Tracks high-water-mark equity for diagnostics. The 15% drawdown
circuit-breaker has been removed; `is_new_entry_allowed()` always returns
True. We're keeping the class so the orchestrator and exit engine can
still query `drawdown` for logging.
"""

import config


class RiskManager:
    def __init__(self, algorithm):
        self._algo = algorithm
        self.hwm: float = 0.0
        self.current_equity: float = 0.0

    def update(self, equity: float) -> None:
        self.current_equity = equity
        if equity > self.hwm:
            self.hwm = equity

    @property
    def drawdown(self) -> float:
        if self.hwm <= 0:
            return 0.0
        return (self.hwm - self.current_equity) / self.hwm

    def is_new_entry_allowed(self) -> bool:
        # Drawdown gate disabled — always allow new entries.
        return True
