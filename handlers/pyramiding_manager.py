"""
handlers/pyramiding_manager.py — Equal-size leg sizing.

shares_per_leg = floor(INITIAL_LEG_SIZE_PCT * portfolio_value / price)

`portfolio_value` is total_portfolio_value (equity + cash) at the moment of
sizing, so leg size stays proportional to account size regardless of how
much capital is currently deployed.  A separate cash-sufficiency guard in
main.py prevents orders that exceed available free cash.

Adds capped at PYRAMID_MAX_ADDS (i.e., max legs = 1 + PYRAMID_MAX_ADDS).
"""

import math

import config


class PyramidingManager:
    def __init__(self, algorithm):
        self._algo = algorithm

    def size_leg(self, price: float, portfolio_value: float) -> int:
        if price <= 0 or portfolio_value <= 0:
            return 0
        notional = config.INITIAL_LEG_SIZE_PCT * portfolio_value
        return int(math.floor(notional / price))

    def can_add_more(self, leg_count: int) -> bool:
        # leg_count includes initial leg; PYRAMID_MAX_ADDS is the number of *adds*
        # so total legs allowed = 1 + PYRAMID_MAX_ADDS.
        return leg_count < (1 + config.PYRAMID_MAX_ADDS)
