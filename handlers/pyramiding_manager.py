"""
handlers/pyramiding_manager.py — Equal-size leg sizing for option contracts.

contracts_per_leg = floor(OPTION_PREMIUM_LEG_BUDGET_PCT * cash_value /
                          (mid_premium * OPTION_CONTRACT_MULTIPLIER))

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

    def size_leg(self, mid_premium: float, cash_value: float) -> int:
        """Return number of CONTRACTS to buy for a single leg."""
        if mid_premium <= 0 or cash_value <= 0:
            return 0
        budget = config.OPTION_PREMIUM_LEG_BUDGET_PCT * cash_value
        cost_per_contract = mid_premium * config.OPTION_CONTRACT_MULTIPLIER
        if cost_per_contract <= 0:
            return 0
        return int(math.floor(budget / cost_per_contract))

    def can_add_more(self, leg_count: int) -> bool:
        # leg_count includes initial leg; PYRAMID_MAX_ADDS is the number of *adds*
        # so total legs allowed = 1 + PYRAMID_MAX_ADDS.
        return leg_count < (1 + config.PYRAMID_MAX_ADDS)
