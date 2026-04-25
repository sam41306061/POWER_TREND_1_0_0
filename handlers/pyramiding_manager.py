"""
handlers/pyramiding_manager.py — Equal-size leg sizing.

shares_per_leg = floor(INITIAL_LEG_SIZE_PCT * cash_value / price)

`cash_value` is the account's CURRENT free cash at the moment of sizing.
Using cash (not total portfolio value) means each new order organically
shrinks the next leg's size, preventing over-leveraging into the universe.

Adds capped at PYRAMID_MAX_ADDS (i.e., max legs = 1 + PYRAMID_MAX_ADDS).
"""

import math

import config


class PyramidingManager:
    def __init__(self, algorithm):
        self._algo = algorithm

    def size_leg(self, price: float, cash_value: float) -> int:
        if price <= 0 or cash_value <= 0:
            return 0
        notional = config.INITIAL_LEG_SIZE_PCT * cash_value
        return int(math.floor(notional / price))

    def can_add_more(self, leg_count: int) -> bool:
        # leg_count includes initial leg; PYRAMID_MAX_ADDS is the number of *adds*
        # so total legs allowed = 1 + PYRAMID_MAX_ADDS.
        return leg_count < (1 + config.PYRAMID_MAX_ADDS)
