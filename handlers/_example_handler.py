"""
handlers/_example_handler.py — Handler Pattern Reference

This file demonstrates the handler pattern used throughout the template.
Every handler follows these rules:
  1. Constructor receives `algorithm` (the QCAlgorithm reference) — never imported
  2. No LEAN SDK imports — handlers are pure Python
  3. Business logic is testable without LEAN runtime
  4. All thresholds come from config.py — never hardcoded

Copy this file as a starting point for new handlers.
"""

import config


class ExampleHandler:
    """
    Example handler demonstrating the dependency-injection pattern.

    Args:
        algorithm: The QCAlgorithm instance (injected, not imported)
    """

    def __init__(self, algorithm):
        self._algo = algorithm

    def example_method(self, symbol, price: float) -> dict:
        """
        Example method showing the input/output contract pattern.

        Args:
            symbol: Equity Symbol object
            price: Current price

        Returns:
            dict with results of the computation
        """
        # Access algorithm services via self._algo (injected reference)
        self._algo.debug(f"[EXAMPLE] Processing {symbol} @ {price}")

        # Access config thresholds (imported at top of file, not hardcoded)
        max_positions = config.MAX_POSITIONS_OPEN

        return {
            "symbol": str(symbol),
            "price": price,
            "passed": price > 0,
        }
