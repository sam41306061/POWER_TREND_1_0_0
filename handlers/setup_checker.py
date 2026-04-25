"""
handlers/setup_checker.py — Two-Phase Validation

Responsibility:
  Phase 1 (validate_setup):    EOD/scan-time validation — stable daily data.
  Phase 2 (check_entry_trigger): Intraday re-confirmation before placing orders.

Contract:
  validate_setup(symbol, price) → dict        {"valid": bool, "details": dict}
  check_entry_trigger(symbol, price) → bool   True if entry is confirmed
"""

import config


class SetupChecker:
    """Two-phase entry validation: scan-time + entry-time gates."""

    def __init__(
        self,
        algorithm,
        data_handler,
        technical_validator=None,
        instrument_selector=None,
        option_analytics=None,
    ):
        self._algo = algorithm
        self._data_handler = data_handler
        self._technical_validator = technical_validator
        self._instrument_selector = instrument_selector
        self._option_analytics = option_analytics

    def validate_setup(self, symbol, price: float) -> dict:
        """
        Phase 1: Scan-time validation.

        TODO: Implement your setup validation gates. Examples:
          - Event proximity check (within MIN/MAX_DAYS_TO_EVENT window)
          - Market regime check (SPY above EMA/SMA)
          - Technicals pass all mandatory filters
          - Liquidity check (sufficient volume/OI)
          - Historical pattern check (track record)

        Returns:
            {"valid": bool, "details": {"gate_name": pass/fail, ...}}
        """
        details = {}

        # TODO: Add your Phase 1 gates here
        # Example:
        # details["market_regime"] = self._check_market_regime()
        # details["technicals"] = all_technicals_pass
        # details["event_window"] = days_to_event_in_range

        valid = all(details.values()) if details else False
        return {"valid": valid, "details": details}

    def check_entry_trigger(self, symbol, price: float, prior_bar=None) -> bool:
        """
        Phase 2: Intraday entry trigger confirmation.

        Called after Phase 1 passes, at ENTRY_TRIGGER_TIME.
        Re-validates critical conditions with live intraday data.

        TODO: Implement your Phase 2 confirmation logic. Examples:
          - Price still near entry zone (within X% of target EMA)
          - Intraday momentum confirmation
          - No adverse gap

        Returns:
            True if entry is confirmed.
        """
        # TODO: Implement entry trigger logic
        return False
