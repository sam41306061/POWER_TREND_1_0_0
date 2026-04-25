"""
handlers/technical_validator.py — Technical Filter Validation

Responsibility:
  Accept an indicator dict and validate entry conditions.
  Return a structured dict of {filter_name: bool} for each check.

Contract:
  validate_daily_technicals(symbol, price, indicators) → dict[str, bool]
"""

import config


class TechnicalValidator:
    """Validate technical conditions for entry eligibility."""

    def __init__(self, algorithm):
        self._algo = algorithm

    def validate_daily_technicals(
        self, symbol, price: float, indicators: dict
    ) -> dict[str, bool]:
        """
        Run all technical validation filters.

        Args:
            symbol: Equity Symbol object
            price: Current price
            indicators: Dict from DataHandler.get_indicators()

        Returns:
            dict of {filter_name: bool} — True means condition is satisfied.

            TODO: Add your strategy's specific filters. Examples:
              - "above_sma": price > SMA
              - "ema_stack": short EMA > mid EMA > long EMA
              - "not_overextended": price not too far above mean
              - "rsi_oversold": RSI < threshold (for mean-reversion)
        """
        results = {}

        sma = indicators.get("sma_long", 0)
        results["above_sma"] = price > sma if config.PRICE_ABOVE_SMA_REQUIRED else True

        atr = indicators.get("atr", 0)
        atr_mean = indicators.get("atr_mean", 0)
        if atr_mean > 0 and atr > 0:
            extension = (price - sma) / atr if atr > 0 else 0
            results["not_overextended"] = extension < config.MAX_ATR_EXTENSION
        else:
            results["not_overextended"] = True

        # TODO: Add additional filters for your strategy
        # results["ema_stack"] = (
        #     indicators.get("ema_short", 0) > indicators.get("ema_mid", 0)
        #     > indicators.get("ema_long", 0)
        # )

        return results
