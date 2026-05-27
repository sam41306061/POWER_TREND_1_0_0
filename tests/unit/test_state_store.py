"""tests/unit/test_state_store.py — ObjectStore persistence + rehydration."""

import json
from datetime import date, datetime

import pytest

import config
from handlers.position_manager import PositionManager
from handlers.regime_filter import RegimeFilter
from handlers.risk_manager import RiskManager
from handlers.state_store import (
    OBJECT_STORE_KEY,
    STATE_SCHEMA_VERSION,
    StateStore,
    build_snapshot,
)


def _populate(algo):
    """Fill handlers with realistic, distinctive state."""
    pm = PositionManager(algo)
    pm.add_leg("AAPL", 150.0, 10, date(2026, 5, 20))
    pm.add_leg("AAPL", 155.0, 10, date(2026, 5, 22))
    pm.add_leg("MSFT", 400.0, 5, date(2026, 5, 21))

    rm = RiskManager(algo)
    rm.update(105_000.0)
    rm.update(102_000.0)  # creates a non-zero drawdown

    rf = RegimeFilter(algo)
    rf.days_low_above_ema21 = 12
    rf.days_ema21_above_sma50 = 7
    rf.sma50_rising = True
    rf.is_blue_bar = True
    rf.current_state = config.REGIME_TREND_UP
    rf._last_update_date = date(2026, 5, 26)

    return pm, rm, rf


class TestSnapshot:
    def test_snapshot_is_json_safe_and_versioned(self, mock_algorithm):
        mock_algorithm.time = datetime(2026, 5, 26, 9, 35)
        pm, rm, rf = _populate(mock_algorithm)

        payload = build_snapshot(pm, rm, rf)

        # JSON round-trip must succeed without custom encoders.
        text = json.dumps(payload)
        decoded = json.loads(text)

        assert decoded["version"] == STATE_SCHEMA_VERSION
        assert "saved_at" in decoded
        assert set(decoded["positions"].keys()) == {"AAPL", "MSFT"}
        assert decoded["risk"]["high_water_mark"] == pytest.approx(105_000.0)
        assert decoded["regime"]["current_state"] == config.REGIME_TREND_UP
        assert decoded["regime"]["last_update_date"] == "2026-05-26"

    def test_snapshot_preserves_multi_leg_avg_entry(self, mock_algorithm):
        mock_algorithm.time = datetime(2026, 5, 26, 9, 35)
        pm, rm, rf = _populate(mock_algorithm)

        payload = build_snapshot(pm, rm, rf)
        aapl = payload["positions"]["AAPL"]

        assert aapl["leg_count"] == 2
        assert aapl["total_quantity"] == 20
        assert aapl["avg_entry_price"] == pytest.approx(152.5)
        assert aapl["last_leg_date"] == "2026-05-22"
        assert len(aapl["legs"]) == 2


class TestSaveLoadRoundTrip:
    def test_save_then_load_returns_equivalent_payload(self, mock_algorithm):
        mock_algorithm.time = datetime(2026, 5, 26, 9, 35)
        pm, rm, rf = _populate(mock_algorithm)
        store = StateStore(mock_algorithm)

        store.save(pm, rm, rf)
        assert mock_algorithm.object_store.contains_key(OBJECT_STORE_KEY)

        loaded = store.load()
        assert loaded is not None
        assert loaded["version"] == STATE_SCHEMA_VERSION
        assert loaded["positions"]["AAPL"]["total_quantity"] == 20

    def test_load_missing_key_returns_none(self, mock_algorithm):
        store = StateStore(mock_algorithm)
        assert store.load() is None

    def test_load_corrupt_json_returns_none(self, mock_algorithm):
        mock_algorithm.object_store.save(OBJECT_STORE_KEY, "{not valid json")
        store = StateStore(mock_algorithm)
        assert store.load() is None

    def test_load_version_mismatch_returns_none(self, mock_algorithm):
        bad = {"version": STATE_SCHEMA_VERSION + 99, "positions": {}, "risk": {}, "regime": {}}
        mock_algorithm.object_store.save(OBJECT_STORE_KEY, json.dumps(bad))
        store = StateStore(mock_algorithm)
        assert store.load() is None


class TestRehydrate:
    def test_rehydrate_restores_positions_risk_regime(self, mock_algorithm):
        mock_algorithm.time = datetime(2026, 5, 26, 9, 35)
        src_pm, src_rm, src_rf = _populate(mock_algorithm)
        store = StateStore(mock_algorithm)
        store.save(src_pm, src_rm, src_rf)

        # Fresh handlers — simulate a cold restart.
        new_pm = PositionManager(mock_algorithm)
        new_rm = RiskManager(mock_algorithm)
        new_rf = RegimeFilter(mock_algorithm)

        payload = store.load()
        assert payload is not None
        summary = store.rehydrate(
            payload,
            position_manager=new_pm,
            risk_manager=new_rm,
            regime_filter=new_rf,
        )

        assert summary["positions_restored"] == 2
        assert new_pm.open_count == 2
        aapl = new_pm.get_trade("AAPL")
        assert aapl is not None
        assert aapl.total_quantity == 20
        assert aapl.avg_entry_price == pytest.approx(152.5)
        assert aapl.leg_count == 2
        assert aapl.last_leg_date == date(2026, 5, 22)

        assert new_rm.high_water_mark == pytest.approx(105_000.0)
        assert new_rf.current_state == config.REGIME_TREND_UP
        assert new_rf.days_low_above_ema21 == 12
        assert new_rf._last_update_date == date(2026, 5, 26)

    def test_rehydrate_drops_positions_broker_no_longer_holds(self, mock_algorithm):
        mock_algorithm.time = datetime(2026, 5, 26, 9, 35)
        src_pm, src_rm, src_rf = _populate(mock_algorithm)
        store = StateStore(mock_algorithm)
        store.save(src_pm, src_rm, src_rf)

        new_pm = PositionManager(mock_algorithm)
        new_rm = RiskManager(mock_algorithm)
        new_rf = RegimeFilter(mock_algorithm)

        payload = store.load()
        # Broker says: AAPL still held (20 shares), MSFT flat (0).
        store.rehydrate(
            payload,
            position_manager=new_pm,
            risk_manager=new_rm,
            regime_filter=new_rf,
            broker_quantities={"AAPL": 20, "MSFT": 0},
        )

        assert new_pm.open_count == 1
        assert new_pm.has_position("AAPL")
        assert not new_pm.has_position("MSFT")
