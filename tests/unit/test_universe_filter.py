"""Unit tests for handlers.universe_filter.DynamicUniverseSelector."""

from datetime import date, timedelta

import pytest

import config
from handlers.universe_filter import DynamicUniverseSelector


class _Coarse:
    def __init__(self, sym, price, dollar_volume, has_fundamental_data=True):
        self.symbol = sym
        self.price = price
        self.dollar_volume = dollar_volume
        self.has_fundamental_data = has_fundamental_data


def _make_coarse(n: int, include_qqq: bool = True):
    rows = []
    for i in range(n):
        rows.append(
            _Coarse(f"SYM{i}", price=50.0, dollar_volume=(n - i) * 100_000_000)
        )
    if include_qqq:
        rows.append(_Coarse(config.REGIME_SYMBOL, price=400.0, dollar_volume=10_000_000_000))
    return rows


def test_filters_by_price_floor(algo):
    sel = DynamicUniverseSelector(algo)
    coarse = [
        _Coarse("LOW", price=config.MIN_PRICE - 1, dollar_volume=1e9),
        _Coarse("OK", price=config.MIN_PRICE + 1, dollar_volume=1e9),
    ]
    out = sel.select_coarse(coarse)
    assert "OK" in out
    assert "LOW" not in out


def test_filters_by_dollar_volume_floor(algo):
    sel = DynamicUniverseSelector(algo)
    coarse = [
        _Coarse("LIQ", price=50, dollar_volume=config.MIN_DOLLAR_VOLUME * 2),
        _Coarse("ILLIQ", price=50, dollar_volume=config.MIN_DOLLAR_VOLUME / 2),
    ]
    out = sel.select_coarse(coarse)
    assert "LIQ" in out
    assert "ILLIQ" not in out


def test_top_n_selection(algo):
    sel = DynamicUniverseSelector(algo)
    coarse = _make_coarse(config.UNIVERSE_TOP_N + 50, include_qqq=False)
    out = sel.select_coarse(coarse)
    # Top-N + force-included QQQ (added because not in coarse)
    assert len(out) == config.UNIVERSE_TOP_N
    # Highest dollar-volume should be included
    assert "SYM0" in out


def test_qqq_force_included_when_missing(algo):
    sel = DynamicUniverseSelector(algo)
    coarse = _make_coarse(5, include_qqq=False) + [
        _Coarse(config.REGIME_SYMBOL, price=400.0, dollar_volume=1.0),  # below floor
    ]
    out = sel.select_coarse(coarse)
    assert config.REGIME_SYMBOL in out


def test_qqq_not_duplicated_when_already_in_top(algo):
    sel = DynamicUniverseSelector(algo)
    coarse = _make_coarse(5, include_qqq=True)
    out = sel.select_coarse(coarse)
    assert sum(1 for s in out if s == config.REGIME_SYMBOL) == 1


def test_cache_respects_refresh_cadence(algo):
    sel = DynamicUniverseSelector(algo)
    coarse_a = _make_coarse(3, include_qqq=False)
    out_a = sel.select_coarse(coarse_a)

    # Advance less than refresh window — should hit cache
    algo.time = algo.time + timedelta(days=config.UNIVERSE_REFRESH_DAYS - 1)
    out_b = sel.select_coarse([_Coarse("DIFFERENT", price=500, dollar_volume=1e10)])
    assert out_b == out_a

    # Advance past refresh window — should re-rank
    algo.time = algo.time + timedelta(days=2)
    out_c = sel.select_coarse([_Coarse("DIFFERENT", price=500, dollar_volume=1e10)])
    assert out_c != out_a
