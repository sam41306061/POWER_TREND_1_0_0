"""
handlers/risk_manager.py — Account drawdown gate.

Tracks high-water-mark equity. Blocks new entries (initial + adds) when
drawdown from HWM >= MAX_ACCOUNT_DRAWDOWN_PCT.
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
        return self.drawdown < config.MAX_ACCOUNT_DRAWDOWN_PCT
