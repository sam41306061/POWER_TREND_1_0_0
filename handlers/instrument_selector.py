"""
handlers/instrument_selector.py — Contract/Instrument Selection

Responsibility:
  Select the optimal instrument (option contract, equity, etc.) for entry.
  Apply liquidity gates (OI, spread, volume).

Contract:
  select_instrument(symbol) → OptionContract | None
"""

import config


class InstrumentSelector:
    """Select the best instrument for entry based on configurable criteria."""

    def __init__(self, algorithm):
        self._algo = algorithm

    def select_instrument(self, symbol):
        """
        Select the optimal instrument for the given underlying symbol.

        TODO: Implement instrument selection logic. For options strategies:
          1. Get the option chain from self._algo.option_chain(symbol)
          2. Filter by expiry (e.g., nearest weekly on or after target event)
          3. Filter by right (Call/Put depending on strategy)
          4. Rank by distance from TARGET_DELTA
          5. Apply liquidity gates: OI >= MIN_OPEN_INTEREST_MULTIPLIER * FIXED_CONTRACTS
          6. Apply spread gate: (ask - bid) / mid < max_spread_pct

        Returns:
            OptionContract or None if no valid contract found.
        """
        # TODO: Implement
        return None
