"""
type_stubs.py — Platform Type Stubs for Local Testing

Responsibility:
  Provide Python reimplementations of all QuantConnect/LEAN types
  so handlers can be tested locally without the LEAN SDK installed.

Usage:
  Imported by tests/conftest.py and injected as sys.modules["AlgorithmImports"]
  Handlers then "from AlgorithmImports import *" and get stubs instead of LEAN types.

Key Stubs:
  - Symbol: singleton cache
  - QCAlgorithm: base class with all methods handlers call
  - Resolution: enum
  - OrderStatus, OrderDirection: enums
  - SecurityType, TimeValue: enums
  - TradeBar, QuoteBar: market data
  - OrderEvent: order callback data
  - Slice: on_data() payload with .bars, .option_chains
  - OptionUniverse: daily dataset with implied_volatility, open_interest, greeks
  - _DateRules / _TimeRules: schedule.on() rule builders
"""

from enum import Enum
from datetime import datetime, date as _date


# ============================================================================
# SYMBOL (Singleton Cache)
# ============================================================================

class Symbol:
    """Singleton Symbol cache — each unique symbol string has one Symbol object."""
    _cache = {}

    def __new__(cls, value: str):
        if value not in cls._cache:
            instance = super().__new__(cls)
            instance.value = value
            cls._cache[value] = instance
        return cls._cache[value]

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"Symbol({self.value!r})"

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if isinstance(other, Symbol):
            return self.value == other.value
        return self.value == other


# ============================================================================
# ENUMS
# ============================================================================

class Resolution(Enum):
    """Data resolution enum."""
    MINUTE = "minute"
    DAILY = "daily"
    HOUR = "hour"


class OrderStatus(Enum):
    """Order status enum."""
    NEW = "new"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PENDING_SUBMISSION = "pending_submission"
    PENDING_CANCEL = "pending_cancel"
    CANCELED = "canceled"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    INVALID = "invalid"


class OrderDirection(Enum):
    """Order direction enum."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class SecurityType(Enum):
    """Security type enum."""
    EQUITY = "equity"
    OPTION = "option"
    FUTURE = "future"
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"


class TimeValue(Enum):
    """Time value enum for scheduling."""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


class DataNormalizationMode(Enum):
    """Data normalization enum (RAW, ADJUSTED, SPLIT_ADJUSTED, TOTAL_RETURN)."""
    RAW = "raw"
    ADJUSTED = "adjusted"
    SPLIT_ADJUSTED = "split_adjusted"
    TOTAL_RETURN = "total_return"


class Market:
    """Market venue identifier."""
    USA = "usa"


class _UniverseSettings:
    """Stub for QCAlgorithm.universe_settings."""
    def __init__(self):
        self.resolution = Resolution.DAILY
        self.data_normalization_mode = DataNormalizationMode.RAW


# ============================================================================
# SCHEDULING RULE BUILDERS
# ============================================================================

class _DateRules:
    """Stub for QCAlgorithm.date_rules — builds date-based schedule rules."""

    def every_day(self, symbol=None):
        return type("DateRule", (), {})()

    def week_start(self, days_offset: int = 0):
        return type("DateRule", (), {})()

    def month_start(self, days_offset: int = 0):
        return type("DateRule", (), {})()


class _TimeRules:
    """Stub for QCAlgorithm.time_rules — builds time-based schedule rules."""

    def before_market_close(self, symbol, minutes: int = 0):
        return type("TimeRule", (), {})()

    def after_market_open(self, symbol, minutes: int = 0):
        return type("TimeRule", (), {})()

    def at(self, hour: int, minute: int):
        return type("TimeRule", (), {})()


# ============================================================================
# SLICE (on_data payload)
# ============================================================================

class Slice:
    """
    QC Slice — the data container passed to on_data().

    .bars            dict-like {Symbol: TradeBar}  equity bars for this step
    .option_chains   dict-like {Symbol: list[OptionContract]}  chains for subscribed options
    .get(symbol)     convenience accessor that checks .bars first
    """

    def __init__(self, bars=None, option_chains=None):
        self.bars = bars or {}
        self.option_chains = option_chains or {}

    def get(self, symbol):
        """Return the TradeBar for *symbol* (tries str and Symbol key forms)."""
        return self.bars.get(symbol) or self.bars.get(str(symbol))


# ============================================================================
# MARKET DATA TYPES
# ============================================================================

class TradeBar:
    """OHLCV bar."""
    def __init__(self, time: datetime, symbol: str, open: float, high: float,
                 low: float, close: float, volume: int):
        self.time = time
        self.symbol = symbol
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume


class QuoteBar:
    """Bid/ask bar."""
    def __init__(self, time: datetime, symbol: str, bid: float, bid_size: int,
                 ask: float, ask_size: int):
        self.time = time
        self.symbol = symbol
        self.bid = bid
        self.bid_size = bid_size
        self.ask = ask
        self.ask_size = ask_size


# ============================================================================
# ORDER & FILL TYPES
# ============================================================================

class OrderEvent:
    """Order event (fill, reject, cancel callback)."""
    def __init__(self, order_id: int, symbol: str, status: OrderStatus,
                 fill_quantity: float = 0.0, fill_price: float = 0.0,
                 direction: OrderDirection = OrderDirection.BUY,
                 message: str = ""):
        self.order_id = order_id
        self.symbol = symbol
        self.status = status
        self.fill_quantity = fill_quantity
        self.fill_price = fill_price
        self.direction = direction
        self.message = message  # Populated by QC on INVALID / CANCELED orders


class OrderTicket:
    """Order ticket returned from order placement."""
    _next_order_id = 1

    def __init__(self, symbol: str, quantity: int):
        self.order_id = OrderTicket._next_order_id
        OrderTicket._next_order_id += 1
        self.symbol = symbol
        self.quantity = quantity
        self.status = OrderStatus.SUBMITTED


# ============================================================================
# OPTION CONTRACT
# ============================================================================

class _Greeks:
    """Option Greeks container."""
    def __init__(self, delta: float = 0.0, gamma: float = 0.0,
                 theta: float = 0.0, vega: float = 0.0, rho: float = 0.0):
        self.Delta = delta
        self.Gamma = gamma
        self.Theta = theta
        self.Vega = vega
        self.Rho = rho


class OptionContract:
    """Option contract from an options chain."""
    def __init__(self, symbol: str, underlying_symbol: str, strike: float,
                 expiry: datetime, right: str = "Call",
                 delta: float = 0.20, gamma: float = 0.01,
                 theta: float = -0.05, vega: float = 0.10,
                 open_interest: int = 500,
                 bid: float = 2.45, ask: float = 2.55,
                 last_price: float = 2.50, volume: int = 100):
        self.Symbol = symbol
        self.UnderlyingSymbol = underlying_symbol
        self.Strike = strike
        self.Expiry = expiry
        self.Right = right           # "Call" or "Put"
        self.Greeks = _Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega)
        self.OpenInterest = open_interest
        self.BidPrice = bid
        self.AskPrice = ask
        self.LastPrice = last_price
        self.Volume = volume
        # Lower-case aliases for test convenience
        self.strike = strike
        self.expiry = expiry
        self.right = right
        self.delta = delta
        self.bid = bid
        self.ask = ask
        self.price = last_price
        self.open_interest = open_interest


# ============================================================================
# OPTION UNIVERSE (daily dataset — pre-market, OptionUniverse API)
# ============================================================================

class _GreeksUniverse:
    """Greeks container for OptionUniverse daily records."""
    def __init__(self, delta: float = 0.0, gamma: float = 0.0,
                 theta: float = 0.0, vega: float = 0.0):
        self.delta = delta
        self.gamma = gamma
        self.theta = theta
        self.vega = vega


class OptionUniverse:
    """
    Daily options dataset entry — returned by self.option_chain() pre-market.

    In QC production this is a QuantConnect.Data.Market.OptionUniverse object.
    Key differences from OptionContract:
      - implied_volatility is a decimal (0.35 = 35%), not a percentage
      - greeks attributes are lower-case (greeks.delta) not Greeks.Delta
      - open_interest is a lower-case attribute
    """

    def __init__(self, symbol: str, underlying_symbol: str, strike: float,
                 expiry, right: str = "Call",
                 implied_volatility: float = 0.25, open_interest: int = 500,
                 delta: float = 0.20, gamma: float = 0.01,
                 theta: float = -0.05, vega: float = 0.10,
                 bid: float = 2.45, ask: float = 2.55,
                 last_price: float = 2.50, volume: int = 100):
        self.Symbol = symbol
        self.UnderlyingSymbol = underlying_symbol
        self.Strike = strike
        self.Expiry = expiry
        self.Right = right
        # Daily dataset uses lower-case, decimal IV (0.25 = 25%)
        self.implied_volatility = implied_volatility
        self.open_interest = open_interest
        self.greeks = _GreeksUniverse(delta=delta, gamma=gamma, theta=theta, vega=vega)
        self.BidPrice = bid
        self.AskPrice = ask
        self.LastPrice = last_price
        self.Volume = volume
        # Convenience aliases
        self.strike = strike
        self.expiry = expiry
        self.right = right
        self.bid = bid
        self.ask = ask
        self.price = last_price


# ============================================================================
# OBJECT STORE
# ============================================================================

class ObjectStore:
    """Stub QC ObjectStore for local testing."""

    def __init__(self):
        self._store: dict = {}
        self.max_size: int = 10_737_418_240  # 10 GB
        self.max_files: int = 10_000
        self.error_raised: bool = False

    def contains_key(self, key: str) -> bool:
        return key in self._store

    @property
    def keys(self):
        return list(self._store.keys())

    def read(self, key: str) -> str:
        val = self._store.get(key, "")
        return val if isinstance(val, str) else val.decode()

    def save(self, key: str, text: str) -> None:
        self._store[key] = text

    def read_bytes(self, key: str) -> bytes:
        val = self._store.get(key, b"")
        return val if isinstance(val, (bytes, bytearray)) else val.encode()

    def save_bytes(self, key: str, data) -> None:
        self._store[key] = bytes(data)

    def get_file_path(self, key: str) -> str:
        import tempfile
        if key not in self._store:
            raise KeyError(key)
        content = self._store[key]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
        tmp.write(content.encode() if isinstance(content, str) else content)
        tmp.close()
        return tmp.name

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def clear(self) -> None:
        self._store.clear()


# ============================================================================
# PORTFOLIO & SECURITY TYPES
# ============================================================================

class Security:
    """Security holding."""
    def __init__(self, symbol: str, price: float = 0.0, quantity: int = 0):
        self.symbol = symbol
        self.price = price
        self.quantity = quantity


class Portfolio:
    """Portfolio holdings and cash."""
    def __init__(self, cash: float = 100_000):
        self.cash = cash
        self.invested = False
        self.margin_remaining = cash  # Available margin; mirrors cash for cash accounts
        self._holdings = {}  # {symbol: Security}

    @property
    def total_portfolio_value(self) -> float:
        """Total portfolio value: cash + sum of position market values."""
        holdings_value = sum(
            h.price * h.quantity for h in self._holdings.values()
        )
        return self.cash + holdings_value

    def __getitem__(self, symbol):
        if symbol not in self._holdings:
            self._holdings[symbol] = Security(symbol)
        return self._holdings[symbol]

    def get(self, symbol, default=None):
        return self._holdings.get(symbol, default)


# ============================================================================
# ALGORITHM BASE CLASS
# ============================================================================

class _OptionChainProvider:
    """Stub for QCAlgorithm.OptionChainProvider — returns chains from algorithm slot."""

    def __init__(self, algorithm):
        self._algorithm = algorithm

    def get_option_contract_list(self, symbol, date=None):
        """Return list of option contract symbols for the underlying."""
        return self._algorithm.option_chains.get(str(symbol), [])

    def GetOptionContractList(self, symbol, date=None):
        """PascalCase alias for get_option_contract_list() — matches live QC API."""
        return self.get_option_contract_list(symbol, date)


class QCAlgorithm:
    """Stub QCAlgorithm base class for local testing."""

    def __init__(self):
        self.time = datetime.now()
        self.portfolio = Portfolio()
        self.securities = {}  # {symbol: Security}
        self._universe = set()
        self.settings = type("Settings", (), {"seed_initial_prices": True})()
        # is_warming_up: True while set_warm_up() period is being replayed.
        # Guard on_data() with: if self.is_warming_up: return
        self.is_warming_up: bool = False
        # Scheduling rule builders (mirrors QC's date_rules / time_rules API)
        self.date_rules = _DateRules()
        self.time_rules = _TimeRules()
        # ---- Injectable test data slots ----
        # event_data: {symbol_str: {"date": date, "type": str}}  -- e.g. earnings, dividends
        self.event_data = {}
        self.earnings_data = self.event_data  # alias for earnings-based strategies
        # iv_data: {symbol_str: float}  -- current IV value
        self.iv_data = {}
        # iv_history: {symbol_str: [float, ...]}  -- rolling IV history
        self.iv_history = {}
        # event_history: {symbol_str: [bool, ...]}  -- True if stock rose pre-event
        self.event_history = {}
        self.earnings_history = self.event_history  # alias
        # option_chains: {symbol_str: [OptionContract, ...]}  -- chains per underlying
        self.option_chains = {}
        # object_store: mock ObjectStore for local testing
        self.object_store = ObjectStore()
        # OptionChainProvider: pre-market daily option universe provider
        self.OptionChainProvider = _OptionChainProvider(self)
        # universe_settings: stub for resolution / data_normalization_mode.
        self.universe_settings = _UniverseSettings()

    # --- Time (PascalCase alias mirrors live QC attribute) ---

    @property
    def Time(self) -> datetime:
        """PascalCase alias for self.time (matches live QC API)."""
        return self.time

    @Time.setter
    def Time(self, value: datetime):
        self.time = value

    # --- Portfolio (PascalCase alias) ---

    @property
    def Portfolio(self) -> Portfolio:
        """PascalCase alias for self.portfolio (matches live QC API)."""
        return self.portfolio

    # --- Securities (PascalCase alias) ---

    @property
    def Securities(self) -> dict:
        """PascalCase alias for self.securities (matches live QC API)."""
        return self.securities

    # --- Data Access ---

    def history(self, symbol, bars: int, resolution: Resolution):
        """Fetch historical bars. Override in test fixtures."""
        return None

    def History(self, symbol, bars: int, resolution: Resolution):
        """PascalCase alias for history() — matches live QC API."""
        return self.history(symbol, bars, resolution)

    def get_last_price(self, symbol: str) -> float:
        """Get last known price."""
        return self.securities.get(symbol, Security(symbol)).price

    # --- Orders ---

    def buy(self, symbol, quantity: int) -> OrderTicket:
        """Place a buy order."""
        return OrderTicket(symbol, quantity)

    def sell(self, symbol, quantity: int) -> OrderTicket:
        """Place a sell order."""
        return OrderTicket(symbol, -quantity)

    def market_order(self, symbol, quantity: int) -> OrderTicket:
        """Place a market order."""
        return OrderTicket(symbol, quantity)

    def MarketOrder(self, symbol, quantity: int) -> OrderTicket:
        """PascalCase alias for market_order() — matches live QC API."""
        return self.market_order(symbol, quantity)

    def limit_order(self, symbol, quantity: int, price: float) -> OrderTicket:
        """Place a limit order."""
        return OrderTicket(symbol, quantity)

    def liquidate(self, symbol: str = None) -> list:
        """Liquidate position(s)."""
        return []

    # --- Options ---

    def option_chain(self, symbol):
        """Get option chain for underlying. Returns from option_chains slot."""
        return self.option_chains.get(str(symbol), [])

    # --- Universe ---

    def add_universe(self, selector):
        """Add a universe selection."""
        return type("Universe", (), {"selected": set()})()

    # --- Scheduling ---

    @property
    def schedule(self):
        """Get scheduler. schedule.on(date_rule, time_rule, func) registers events."""
        class _Scheduler:
            def on(self, date_rule, time_rule, func):
                pass  # No-op in tests; events are not fired automatically
        return _Scheduler()

    # --- Logging ---

    def log(self, msg: str):
        """Log a message."""
        print(f"[LOG] {msg}")

    def Log(self, msg: str):
        """PascalCase alias for log() — matches live QC API."""
        self.log(msg)

    def debug(self, msg: str):
        """Log debug message."""
        print(f"[DEBUG] {msg}")

    def Debug(self, msg: str):
        """PascalCase alias for debug() — matches live QC API."""
        self.debug(msg)

    def error(self, msg: str):
        """Log error message."""
        print(f"[ERROR] {msg}")

    def Error(self, msg: str):
        """PascalCase alias for error() — matches live QC API."""
        self.error(msg)

    # --- Utility ---

    def set_start_date(self, year: int, month: int, day: int):
        """Set backtest start date."""
        pass

    def set_end_date(self, year: int, month: int, day: int):
        """Set backtest end date."""
        pass

    def set_cash(self, amount: float):
        """Set initial cash."""
        self.portfolio.cash = amount
        self.portfolio.margin_remaining = amount

    def add_equity(self, symbol: str, resolution=None) -> "Security":
        """Add equity subscription. Returns Security with .symbol for chaining."""
        sec = Security(symbol)
        self.securities[symbol] = sec
        return sec

    def AddEquity(self, ticker: str, resolution=None) -> "Security":
        """PascalCase alias for add_equity() — matches live QC API."""
        return self.add_equity(ticker, resolution)

    def add_option(self, symbol: str, resolution=None) -> "Security":
        """Add option subscription. Returns Security with .symbol for chaining."""
        sec = Security(symbol)
        self.securities[symbol] = sec
        return sec

    def AddOption(self, ticker: str, resolution=None) -> "Security":
        """PascalCase alias for add_option() — matches live QC API."""
        return self.add_option(ticker, resolution)

    def add_option_contract(self, symbol) -> "Security":
        """
        Subscribe to a specific option contract.
        Returns object with .symbol so callers can do:
            option_symbol = self.add_option_contract(contract_symbol).symbol
        """
        sym_str = str(symbol)
        sec = Security(sym_str)
        self.securities[sym_str] = sec
        return sec

    def set_warm_up(self, n_bars: int) -> None:
        """
        Set warm-up period. Controls the is_warming_up flag during replay.
        Stub records the value but does not replay data — DataHandler tests
        use history injection instead.
        """
        self._warm_up_bars = n_bars

    def warm_up_indicator(self, symbol, indicator) -> None:
        """
        Pre-seed a native QC indicator with historical bars before backtest start.
        Stub does nothing — DataHandler uses history injection instead.
        """
        pass



# ============================================================================
# EVENT DATA STUB (for event-driven calendar testing)
# ============================================================================

class EventData:
    """
    Generic event calendar entry stub.

    Use for any event-driven strategy (earnings, dividends, FOMC, etc.).
    Mirrors the dict-style entries stored in algorithm.event_data:
        algorithm.event_data[symbol] = {"date": date, "type": "BMO"|"AMC"|...}

    This class provides an object-oriented alternative for tests that prefer
    attribute access over dict access.
    """

    def __init__(self, symbol: str, date, event_type: str = "BMO"):
        """
        Args:
            symbol: Underlying equity symbol string (e.g. "AAPL")
            date: Event date as datetime.date or datetime.datetime
            event_type: Event classification (e.g. "BMO", "AMC", "UNCONFIRMED")
        """
        self.symbol = symbol
        self.date = date.date() if isinstance(date, datetime) else date
        self.type = event_type

    def to_dict(self) -> dict:
        """Convert to the dict format used by algorithm.event_data."""
        return {"date": self.date, "type": self.type}


# Backwards-compatible alias
EarningsData = EventData




__all__ = [
    "Symbol",
    "Resolution",
    "OrderStatus",
    "OrderDirection",
    "SecurityType",
    "TimeValue",
    "DataNormalizationMode",
    "Market",
    "TradeBar",
    "QuoteBar",
    "OrderEvent",
    "OrderTicket",
    "Security",
    "Portfolio",
    "QCAlgorithm",
    "OptionContract",
    "OptionUniverse",
    "ObjectStore",
    "EarningsData",
    "EventData",
    "Slice",
    "_Greeks",
    "_GreeksUniverse",
    "_OptionChainProvider",
    "_UniverseSettings",
]
