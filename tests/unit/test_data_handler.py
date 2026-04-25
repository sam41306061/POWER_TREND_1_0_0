"""Unit tests for handlers.data_handler.DataHandler."""

import math

import config
from handlers.data_handler import DataHandler


class _Bar:
    def __init__(self, o, h, l, c, v):
        self.open = o
        self.high = h
        self.low = l
        self.close = c
        self.volume = v


def _trend_bars(n: int = 100, start: float = 100.0, step: float = 0.5):
    bars = []
    p = start
    for _ in range(n):
        o = p
        c = p + step
        h = c + 0.5
        l = o - 0.5
        bars.append(_Bar(o, h, l, c, 1_000_000))
        p = c
    return bars


def test_returns_none_when_history_too_short(algo):
    dh = DataHandler(algo)
    out = dh.get_indicators("X", history=_trend_bars(n=10))
    assert out is None


def test_computes_all_required_fields(algo):
    dh = DataHandler(algo)
    bars = _trend_bars(n=120)
    ind = dh.get_indicators("X", history=bars)
    assert ind is not None
    expected = {
        "close", "open", "low", "prior_close", "prior_low",
        "EMA21", "SMA50", "prior_EMA21", "prior_SMA50",
        "dollar_volume_20d", "atr_14", "atr_stretch_low", "is_blue_bar",
    }
    assert expected <= set(ind.keys())


def test_blue_bar_detection(algo):
    dh = DataHandler(algo)
    bars = _trend_bars(n=120)
    bars[-1] = _Bar(o=200, h=205, l=199, c=204, v=1_000_000)
    ind = dh.get_indicators("X", history=bars)
    assert ind["is_blue_bar"] is True

    bars[-1] = _Bar(o=200, h=205, l=195, c=198, v=1_000_000)
    ind = dh.get_indicators("Y", history=bars)
    assert ind["is_blue_bar"] is False


def test_ema_seed_matches_known_value(algo):
    dh = DataHandler(algo)
    # Constant series → EMA equals the constant
    bars = [_Bar(50, 51, 49, 50, 1) for _ in range(120)]
    ind = dh.get_indicators("X", history=bars)
    assert ind is not None
    assert math.isclose(ind["EMA21"], 50.0, rel_tol=1e-9)
    assert math.isclose(ind["SMA50"], 50.0, rel_tol=1e-9)


def test_cache_returns_same_object_within_day(algo):
    dh = DataHandler(algo)
    bars = _trend_bars(n=120)
    a = dh.get_indicators("CACHED", history=None) is None  # no history -> none
    # populate cache via history-injection won't cache; use without history with mock fetch
    # Direct cache test: place value directly, then assert hit
    dh._cache[("FOO", algo.time.date())] = {"close": 1.0}
    out = dh.get_indicators("FOO")
    assert out == {"close": 1.0}


def test_clear_cache(algo):
    dh = DataHandler(algo)
    dh._cache[("FOO", algo.time.date())] = {"close": 1.0}
    dh.clear_cache()
    assert dh._cache == {}


def test_atr_stretch_low_sign(algo):
    dh = DataHandler(algo)
    bars = _trend_bars(n=120)
    # Force last bar low far below EMA21
    last = bars[-1]
    bars[-1] = _Bar(o=last.open, h=last.high, l=last.close - 50, c=last.close, v=1)
    ind = dh.get_indicators("X", history=bars)
    assert ind["atr_stretch_low"] < 0
