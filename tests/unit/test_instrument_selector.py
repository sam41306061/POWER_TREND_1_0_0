"""Unit tests for handlers.instrument_selector.InstrumentSelector."""

from datetime import date, datetime, timedelta

import config
from handlers.instrument_selector import InstrumentSelector


class _FakeContract:
    def __init__(
        self,
        symbol: str,
        strike: float = 100.0,
        expiry=None,
        right: str = "Call",
        delta: float = 0.70,
        open_interest: int = 500,
        bid: float = 4.95,
        ask: float = 5.05,
    ):
        self.Symbol = symbol
        self.Strike = strike
        self.Expiry = expiry
        self.Right = right
        self.delta = delta
        self.OpenInterest = open_interest
        self.BidPrice = bid
        self.AskPrice = ask
        self.LastPrice = (bid + ask) / 2.0


def _today():
    return date(2024, 1, 15)


def _exp(days):
    return _today() + timedelta(days=days)


def _algo_with_today():
    class _A:
        time = datetime(2024, 1, 15)

        def debug(self, *_):
            pass

    return _A()


def test_selects_closest_to_target_delta():
    sel = InstrumentSelector(_algo_with_today())
    chain = [
        _FakeContract("c1", delta=0.80, expiry=_exp(180)),
        _FakeContract("c2", delta=0.72, expiry=_exp(180)),
        _FakeContract("c3", delta=0.90, expiry=_exp(180)),
    ]
    pick = sel.select("AAPL", chain, today=_today())
    assert pick is not None
    # 0.72 is closest to OPTION_TARGET_DELTA (0.70)
    assert pick.contract_symbol == "c2"


def test_filters_puts():
    sel = InstrumentSelector(_algo_with_today())
    chain = [_FakeContract("p1", right="Put", delta=0.70, expiry=_exp(180))]
    assert sel.select("AAPL", chain, today=_today()) is None


def test_filters_dte_too_short():
    sel = InstrumentSelector(_algo_with_today())
    chain = [_FakeContract("c1", delta=0.70, expiry=_exp(config.OPTION_DTE_MIN - 1))]
    assert sel.select("AAPL", chain, today=_today()) is None


def test_filters_dte_too_long():
    sel = InstrumentSelector(_algo_with_today())
    chain = [_FakeContract("c1", delta=0.70, expiry=_exp(config.OPTION_DTE_MAX + 1))]
    assert sel.select("AAPL", chain, today=_today()) is None


def test_filters_delta_too_low():
    sel = InstrumentSelector(_algo_with_today())
    chain = [_FakeContract("c1", delta=0.50, expiry=_exp(180))]
    assert sel.select("AAPL", chain, today=_today()) is None


def test_filters_delta_too_high():
    sel = InstrumentSelector(_algo_with_today())
    chain = [_FakeContract("c1", delta=0.99, expiry=_exp(180))]
    assert sel.select("AAPL", chain, today=_today()) is None


def test_filters_low_open_interest():
    sel = InstrumentSelector(_algo_with_today())
    chain = [
        _FakeContract(
            "c1", delta=0.70, expiry=_exp(180),
            open_interest=config.OPTION_MIN_OPEN_INTEREST - 1,
        )
    ]
    assert sel.select("AAPL", chain, today=_today()) is None


def test_filters_wide_spread():
    sel = InstrumentSelector(_algo_with_today())
    # mid = 5.0; (ask-bid)/mid > 10%
    chain = [_FakeContract("c1", delta=0.70, expiry=_exp(180), bid=4.50, ask=5.50)]
    assert sel.select("AAPL", chain, today=_today()) is None


def test_returns_record_with_metadata():
    sel = InstrumentSelector(_algo_with_today())
    chain = [
        _FakeContract(
            "c1", strike=120.0, delta=0.72,
            expiry=_exp(180), bid=4.95, ask=5.05,
        )
    ]
    rec = sel.select("AAPL", chain, today=_today())
    assert rec is not None
    assert rec.contract_symbol == "c1"
    assert rec.strike == 120.0
    assert rec.delta == 0.72
    assert abs(rec.mid_price - 5.0) < 1e-9
    assert rec.expiry == _exp(180)
    assert rec.underlying_symbol == "AAPL"


def test_handles_datetime_expiry():
    sel = InstrumentSelector(_algo_with_today())
    chain = [
        _FakeContract(
            "c1", delta=0.70, expiry=datetime.combine(_exp(180), datetime.min.time())
        )
    ]
    rec = sel.select("AAPL", chain, today=_today())
    assert rec is not None
    assert rec.expiry == _exp(180)


def test_negative_delta_treated_as_absolute():
    sel = InstrumentSelector(_algo_with_today())
    # Some platforms expose put-style negative delta on calls; selector uses abs()
    chain = [_FakeContract("c1", delta=-0.72, expiry=_exp(180))]
    rec = sel.select("AAPL", chain, today=_today())
    assert rec is not None
    assert rec.delta == 0.72


def test_empty_chain_returns_none():
    sel = InstrumentSelector(_algo_with_today())
    assert sel.select("AAPL", [], today=_today()) is None
    assert sel.select("AAPL", None, today=_today()) is None


def test_tiebreak_prefers_mid_dte():
    sel = InstrumentSelector(_algo_with_today())
    mid_dte = (config.OPTION_DTE_MIN + config.OPTION_DTE_MAX) // 2
    chain = [
        _FakeContract("near_min", delta=0.70, expiry=_exp(config.OPTION_DTE_MIN + 5)),
        _FakeContract("middle", delta=0.70, expiry=_exp(mid_dte)),
        _FakeContract("near_max", delta=0.70, expiry=_exp(config.OPTION_DTE_MAX - 5)),
    ]
    rec = sel.select("AAPL", chain, today=_today())
    assert rec is not None
    assert rec.contract_symbol == "middle"
