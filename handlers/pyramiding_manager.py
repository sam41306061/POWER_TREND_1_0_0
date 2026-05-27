"""
handlers/pyramiding_manager.py — Equal-size leg sizing for pyramid adds.

Computes share quantity per leg from INITIAL_LEG_SIZE_PCT of portfolio value
and enforces the PYRAMID_MAX_ADDS cap on additional legs.
"""

from math import floor

import config


class PyramidingManager:
    """Compute leg sizing and enforce the pyramid cap."""

    def __init__(self, algorithm):
        self._algo = algorithm

    def compute_leg_size(self, portfolio_value: float, price: float) -> int:
        """Equal-size shares per leg, floored to a whole share."""
        if portfolio_value <= 0 or price <= 0:
            return 0
        dollars = config.INITIAL_LEG_SIZE_PCT * portfolio_value
        return int(floor(dollars / price))

    def can_add(self, trade) -> bool:
        """True iff *trade* still has room for another pyramid add."""
        if trade is None:
            return False
        # leg_count includes the initial leg. The initial leg counts as add #0;
        # PYRAMID_MAX_ADDS is the max ADDITIONAL legs, so total legs ≤ 1 + max.
        return trade.leg_count < (1 + config.PYRAMID_MAX_ADDS)
