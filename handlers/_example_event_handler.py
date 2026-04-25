"""
handlers/_example_event_handler.py — Event-Driven Handler Pattern

This stub replaces strategy-specific event handlers (earnings calendar,
dividend calendar, macro event calendar, etc.) with a generic pattern.

Responsibility:
  Fetch upcoming events for universe symbols.
  Classify event timing (e.g., pre-market / post-market).
  Provide days-until-event lookups.

Contract:
  get_upcoming_events(universe, min_days, max_days) → list[tuple]
  is_event_today(symbol) → bool
  days_until_event(symbol) → int | None

Copy this file and rename to match your event type
(e.g., earnings_calendar.py, dividend_calendar.py).
"""

import config


class EventCalendar:
    """
    Generic event calendar handler.

    TODO: Implement event data retrieval for your strategy.
    Data sources:
      - QuantConnect Fundamental data (earnings, dividends)
      - External API (economic calendar, SEC filings)
      - Static CSV (known event dates)
    """

    def __init__(self, algorithm):
        self._algo = algorithm
        self._cache: dict[str, dict] = {}  # {symbol_str: {"date": date, "type": str}}

    def invalidate_cache(self) -> None:
        """Clear the event cache. Call at the start of each daily scan."""
        self._cache.clear()

    def get_upcoming_events(
        self, universe: set[str], min_days: int = None, max_days: int = None
    ) -> list[tuple]:
        """
        Return symbols with upcoming events within the configured window.

        Args:
            universe: Set of ticker strings to filter
            min_days: Minimum days to event (default: config.MIN_DAYS_TO_EVENT)
            max_days: Maximum days to event (default: config.MAX_DAYS_TO_EVENT)

        Returns:
            List of (symbol, event_date, event_type) tuples
        """
        if min_days is None:
            min_days = config.MIN_DAYS_TO_EVENT
        if max_days is None:
            max_days = config.MAX_DAYS_TO_EVENT

        # TODO: Implement event lookup
        # Example for earnings:
        #   for sym in universe:
        #       fund = self._algo.securities[sym].fundamentals
        #       next_earnings = fund.earning_reports.next_report_date
        #       days = (next_earnings - today).days
        #       if min_days <= days <= max_days:
        #           results.append((sym, next_earnings, "BMO" or "AMC"))

        return []

    def is_event_today(self, symbol: str) -> bool:
        """Check if the target event occurs today for this symbol."""
        # TODO: Implement
        return False

    def days_until_event(self, symbol: str) -> int | None:
        """Return days until the next event, or None if no event scheduled."""
        # TODO: Implement
        return None
