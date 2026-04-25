"""
Example platform adapter — translates a non-LEAN platform API into the
algorithm interface that handlers expect.

Copy this file and implement each method for your target platform.
See docs/PLATFORM_ADAPTERS.md for the full interface contract.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AlgorithmProtocol(Protocol):
    """Minimal interface that all handlers depend on."""

    @property
    def Time(self) -> Any: ...

    @property
    def Portfolio(self) -> Any: ...

    def Log(self, message: str) -> None: ...
    def Debug(self, message: str) -> None: ...
    def Error(self, message: str) -> None: ...
    def History(self, symbol: Any, periods: int, resolution: Any) -> list: ...
    def MarketOrder(self, symbol: Any, quantity: int) -> Any: ...


class ExampleAdapter:
    """
    Adapter template.  Replace ``platform_ctx`` with your platform's context
    object and implement each method.

    Usage::

        adapter = ExampleAdapter(platform_ctx)
        data_handler = DataHandler(adapter)
        validator = TechnicalValidator(adapter)
    """

    def __init__(self, platform_ctx: Any) -> None:
        self._ctx = platform_ctx

    # -- Properties ----------------------------------------------------------

    @property
    def Time(self):
        """Return current simulation / live datetime."""
        raise NotImplementedError("Map to your platform's current-time API")

    @property
    def Portfolio(self):
        """Return portfolio state (positions, cash, value)."""
        raise NotImplementedError("Map to your platform's portfolio API")

    @property
    def Securities(self):
        """Return subscribed securities data."""
        raise NotImplementedError("Map to your platform's securities API")

    # -- Logging -------------------------------------------------------------

    def Log(self, message: str) -> None:
        raise NotImplementedError

    def Debug(self, message: str) -> None:
        raise NotImplementedError

    def Error(self, message: str) -> None:
        raise NotImplementedError

    # -- Data ----------------------------------------------------------------

    def History(self, symbol, periods: int, resolution=None) -> list:
        """Return historical bars as list of TradeBar-like objects."""
        raise NotImplementedError("Map to your platform's history API")

    # -- Orders --------------------------------------------------------------

    def MarketOrder(self, symbol, quantity: int):
        """Place a market order; return an order-ticket-like object."""
        raise NotImplementedError("Map to your platform's order API")
