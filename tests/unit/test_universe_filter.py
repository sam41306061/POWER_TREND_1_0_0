"""tests/unit/test_universe_filter.py — Dynamic top-N universe selector."""

from datetime import datetime, timedelta

import config
from handlers.universe_filter import DynamicUniverseSelector


def _coarse_row(symbol: str, price: float, dollar_volume: float,
                has_fundamental: bool = True):
    obj = type("Coarse", (), {})()
    obj.symbol = symbol
    obj.price = price
    obj.dollar_volume = dollar_volume
    obj.has_fundamental_data = has_fundamental
    return obj


class TestDynamicUniverseSelector:
    def test_filters_by_min_price_and_dollar_volume(self, mock_algorithm):
        sel = DynamicUniverseSelector(mock_algorithm)
        coarse = [
            _coarse_row("AAA", price=config.MIN_PRICE - 1, dollar_volume=1e10),  # rejected: price
            _coarse_row("BBB", price=config.MIN_PRICE + 1, dollar_volume=config.MIN_DOLLAR_VOLUME / 2),  # rejected: $vol
            _coarse_row("CCC", price=config.MIN_PRICE + 1, dollar_volume=config.MIN_DOLLAR_VOLUME * 2),  # kept
            _coarse_row("QQQ", price=400.0, dollar_volume=5e10),  # kept
        ]
        out = sel.coarse_filter(coarse)
        out_str = {str(s) for s in out}
        assert "AAA" not in out_str
        assert "BBB" not in out_str
        assert "CCC" in out_str
        assert "QQQ" in out_str

    def test_ranks_by_dollar_volume_desc_and_caps_top_n(self, mock_algorithm):
        sel = DynamicUniverseSelector(mock_algorithm)
        # Build TOP_N + 5 valid candidates with increasing $vol so the last
        # 5 (lowest $vol) should be dropped.
        coarse = [
            _coarse_row(f"S{i}", price=config.MIN_PRICE + 1,
                        dollar_volume=config.MIN_DOLLAR_VOLUME * (i + 1))
            for i in range(config.UNIVERSE_TOP_N + 5)
        ]
        # No QQQ here — selector should force-add it only if present in coarse.
        out = sel.coarse_filter(coarse)
        # Should keep the highest TOP_N + 0 (no QQQ added since absent from coarse).
        assert len(out) == config.UNIVERSE_TOP_N

    def test_force_includes_qqq_when_outside_top_n(self, mock_algorithm):
        sel = DynamicUniverseSelector(mock_algorithm)
        # TOP_N rows with much higher volume than QQQ → QQQ shouldn't rank.
        coarse = [
            _coarse_row(f"S{i}", price=config.MIN_PRICE + 1,
                        dollar_volume=config.MIN_DOLLAR_VOLUME * 100)
            for i in range(config.UNIVERSE_TOP_N)
        ]
        coarse.append(_coarse_row("QQQ", price=400.0,
                                  dollar_volume=config.MIN_DOLLAR_VOLUME * 2))
        out = sel.coarse_filter(coarse)
        out_str = {str(s) for s in out}
        assert "QQQ" in out_str
        assert len(out) == config.UNIVERSE_TOP_N + 1

    def test_caches_for_refresh_window(self, mock_algorithm):
        sel = DynamicUniverseSelector(mock_algorithm)
        coarse_initial = [
            _coarse_row("AAA", price=100, dollar_volume=config.MIN_DOLLAR_VOLUME * 2),
        ]
        mock_algorithm.time = datetime(2025, 1, 1)
        first = sel.coarse_filter(coarse_initial)

        # 1 day later → still cached, even with a different coarse list.
        mock_algorithm.time = datetime(2025, 1, 2)
        coarse_changed = [
            _coarse_row("BBB", price=100, dollar_volume=config.MIN_DOLLAR_VOLUME * 2),
        ]
        second = sel.coarse_filter(coarse_changed)
        assert second == first

        # After UNIVERSE_REFRESH_DAYS → recomputes.
        mock_algorithm.time = datetime(2025, 1, 1) + timedelta(
            days=config.UNIVERSE_REFRESH_DAYS
        )
        third = sel.coarse_filter(coarse_changed)
        assert {str(s) for s in third} == {"BBB"}
