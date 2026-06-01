"""DynamicUniverseSelector tests."""

from types import SimpleNamespace

import config
from handlers.universe_filter import DynamicUniverseSelector


def _coarse(symbol, price, dollar_volume, has_fundamental_data=True):
    return SimpleNamespace(
        symbol=symbol, price=price, dollar_volume=dollar_volume,
        has_fundamental_data=has_fundamental_data,
    )


def test_filters_by_price_and_dollar_volume(mock_algorithm):
    coarse = [
        _coarse("AAA", price=config.MIN_PRICE - 1, dollar_volume=1e9),
        _coarse("BBB", price=50, dollar_volume=config.MIN_DOLLAR_VOLUME - 1),
        _coarse("CCC", price=50, dollar_volume=config.MIN_DOLLAR_VOLUME + 1),
    ]
    sel = DynamicUniverseSelector(mock_algorithm)
    result = sel.coarse_filter(coarse)
    assert "AAA" not in result
    assert "BBB" not in result
    assert "CCC" in result


def test_top_n_by_dollar_volume(mock_algorithm):
    # 3 valid candidates; top-N caps to UNIVERSE_TOP_N which is large -> all kept
    coarse = [
        _coarse(f"S{i}", 50.0, config.MIN_DOLLAR_VOLUME + i * 1e6)
        for i in range(5)
    ]
    sel = DynamicUniverseSelector(mock_algorithm)
    result = sel.coarse_filter(coarse)
    # Highest $-vol first
    assert result[0] == "S4"


def test_cache_returns_same_universe_within_refresh_window(mock_algorithm):
    coarse = [_coarse("CCC", 50.0, config.MIN_DOLLAR_VOLUME + 1)]
    sel = DynamicUniverseSelector(mock_algorithm)
    first = sel.coarse_filter(coarse)
    # Pass empty list -> should still return cached snapshot
    second = sel.coarse_filter([])
    assert first == second


def test_retain_symbol_keeps_position_in_universe_across_refresh(mock_algorithm):
    """Regression (Bug C2): when a held symbol drops out of the top-N on a
    refresh, force-retaining it must keep it in the universe so QC doesn't
    auto-liquidate behind ExitEngine's back."""
    sel = DynamicUniverseSelector(mock_algorithm)
    # Initial selection includes ZZZ
    coarse_a = [_coarse("ZZZ", 50.0, config.MIN_DOLLAR_VOLUME + 100)]
    sel.coarse_filter(coarse_a)
    assert "ZZZ" in sel.current_universe

    # Suppose ZZZ no longer qualifies on the next refresh window
    sel._last_refresh_date = None  # force re-selection
    sel.retain_symbol("ZZZ")
    coarse_b = [_coarse("AAA", 50.0, config.MIN_DOLLAR_VOLUME + 100)]
    result = sel.coarse_filter(coarse_b)
    assert "ZZZ" in result, "retained symbol must persist across refresh"
    assert "AAA" in result


def test_release_symbol_drops_retention(mock_algorithm):
    sel = DynamicUniverseSelector(mock_algorithm)
    sel.retain_symbol("ZZZ")
    sel.release_symbol("ZZZ")
    # Next refresh without qualifying coarse data should not include ZZZ
    sel._last_refresh_date = None
    result = sel.coarse_filter([_coarse("AAA", 50.0, config.MIN_DOLLAR_VOLUME + 1)])
    assert "ZZZ" not in result
