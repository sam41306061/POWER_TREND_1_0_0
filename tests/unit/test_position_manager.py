"""Unit tests for handlers.position_manager.PositionManager (option legs)."""

from datetime import date

import config
from handlers.position_manager import PositionManager


def _add(pm, sym, premium, contracts, fill_date, **kw):
    return pm.add_leg(
        symbol=sym,
        fill_price=premium,
        quantity=contracts,
        fill_date=fill_date,
        contract_symbol=kw.get("contract_symbol", f"{sym}_OPT_{fill_date.isoformat()}"),
        expiry=kw.get("expiry", date(2024, 7, 19)),
        strike=kw.get("strike", 100.0),
        delta_at_entry=kw.get("delta", 0.70),
        underlying_price_at_entry=kw.get("underlying_price", 100.0),
    )


def test_add_initial_leg_carries_metadata(algo):
    pm = PositionManager(algo)
    trade = _add(pm, "AAPL", 5.00, 10, date(2024, 1, 1))
    assert trade.leg_count == 1
    assert trade.total_quantity == 10
    assert trade.avg_entry_price == 5.00
    leg = trade.legs[0]
    assert leg.expiry == date(2024, 7, 19)
    assert leg.strike == 100.0
    assert leg.delta_at_entry == 0.70
    assert pm.has_position_for_underlying("AAPL")


def test_multiple_legs_different_contracts(algo):
    pm = PositionManager(algo)
    _add(pm, "AAPL", 5.00, 10, date(2024, 1, 1), expiry=date(2024, 7, 19), strike=100.0,
         contract_symbol="AAPL_C1")
    _add(pm, "AAPL", 6.00, 10, date(2024, 1, 5), expiry=date(2024, 9, 20), strike=110.0,
         contract_symbol="AAPL_C2")
    trade = pm.get_trade("AAPL")
    assert trade.leg_count == 2
    assert trade.total_quantity == 20
    assert trade.avg_entry_price == 5.50
    assert trade.last_leg_date == date(2024, 1, 5)
    # legs preserve their own contract identity
    assert {l.strike for l in trade.legs} == {100.0, 110.0}


def test_can_add_position_capacity(algo):
    pm = PositionManager(algo)
    for i in range(config.MAX_POSITIONS_OPEN):
        _add(pm, f"S{i}", 5.0, 1, date(2024, 1, 1))
    assert pm.can_add_position() is False


def test_close_trade_premium_pnl_with_multiplier(algo):
    pm = PositionManager(algo)
    _add(pm, "X", 5.00, 10, date(2024, 1, 1))
    _add(pm, "X", 6.00, 10, date(2024, 1, 5))
    algo.time = algo.time.replace(year=2024, month=1, day=20)
    result = pm.close_trade("X", exit_price=8.00, reason=config.EXIT_REASON_MANUAL)
    assert result is not None
    # leg1: (8 - 5) * 10 * 100 = 3000; leg2: (8 - 6) * 10 * 100 = 2000 -> 5000
    assert result["pnl"] == 5000.0
    assert result["total_quantity"] == 20
    assert "X" not in pm.active_trades


def test_close_leg_partial_then_close_remaining(algo):
    pm = PositionManager(algo)
    leg1 = _add(pm, "X", 5.00, 10, date(2024, 1, 1), contract_symbol="X_C1").legs[0]
    leg2 = _add(pm, "X", 6.00, 10, date(2024, 1, 5), contract_symbol="X_C2").legs[1]
    # Close leg1 only — trade stays open
    result = pm.close_leg("X", leg1, exit_price=7.00, reason=config.EXIT_REASON_DTE_FORCE)
    assert result is not None
    assert result["pnl"] == (7.00 - 5.00) * 10 * config.OPTION_CONTRACT_MULTIPLIER
    assert "X" in pm.active_trades
    trade = pm.get_trade("X")
    assert trade.total_quantity == 10  # only open contracts counted
    assert trade.leg_count == 2  # historical legs preserved
    assert trade.avg_entry_price == 6.00  # only leg2 still open
    # Close the second leg — trade closes
    pm.close_leg("X", leg2, exit_price=4.00, reason=config.EXIT_REASON_PREMIUM_STOP)
    assert "X" not in pm.active_trades
    assert pm.closed_trades[-1].symbol == "X"


def test_find_leg_by_contract(algo):
    pm = PositionManager(algo)
    _add(pm, "AAPL", 5.0, 5, date(2024, 1, 1), contract_symbol="AAPL_240719C")
    _add(pm, "AAPL", 6.0, 5, date(2024, 1, 5), contract_symbol="AAPL_240920C")
    found = pm.find_leg_by_contract("AAPL_240920C")
    assert found is not None
    underlying, leg = found
    assert underlying == "AAPL"
    assert leg.strike == 100.0
    assert pm.find_leg_by_contract("MISSING") is None


def test_close_unknown_trade_returns_none(algo):
    pm = PositionManager(algo)
    assert pm.close_trade("NOPE", 100.0, "X") is None


# ---------------------------------------------------------------------------
# Rename-aware (SID-keyed) identity
# ---------------------------------------------------------------------------

from AlgorithmImports import Symbol  # type: ignore  # noqa: E402


def test_sid_index_tracks_open_trades(algo):
    pm = PositionManager(algo)
    sym = Symbol("AAPL", sid="AAPL-SID-1")
    pm.add_leg(
        symbol="AAPL",
        fill_price=5.0,
        quantity=10,
        fill_date=date(2024, 1, 1),
        contract_symbol="AAPL_C1",
        live_symbol=sym,
    )
    assert pm.has_position_for_sid("AAPL-SID-1")
    assert pm.ticker_for_sid("AAPL-SID-1") == "AAPL"


def test_rename_migrates_trade_record(algo):
    """BEL -> VZ scenario: a second leg arrives under a new ticker but the
    same SID. The existing TradeRecord must be re-keyed under the new ticker
    instead of leaving an orphan slot under the old key."""
    pm = PositionManager(algo)
    bel = Symbol("BEL", sid="VZ-SID-X")
    vz = Symbol("VZ", sid="VZ-SID-X")
    leg1 = pm.add_leg(
        symbol="BEL",
        fill_price=5.0,
        quantity=10,
        fill_date=date(2012, 1, 5),
        contract_symbol="BEL_C1",
        live_symbol=bel,
    ).legs[0]
    assert pm.ticker_for_sid("VZ-SID-X") == "BEL"

    pm.add_leg(
        symbol="VZ",
        fill_price=6.0,
        quantity=10,
        fill_date=date(2012, 5, 20),
        contract_symbol="VZ_C1",
        live_symbol=vz,
    )
    # Old key gone, new key holds the migrated record with BOTH legs.
    assert "BEL" not in pm.active_trades
    assert "VZ" in pm.active_trades
    trade = pm.get_trade("VZ")
    assert trade.leg_count == 2
    assert leg1 in trade.legs
    assert pm.ticker_for_sid("VZ-SID-X") == "VZ"


def test_rename_migrates_in_reverse_direction(algo):
    """Symmetric: the rename can also surface as VZ first, then back to BEL."""
    pm = PositionManager(algo)
    a = Symbol("VZ", sid="VZ-SID-Y")
    b = Symbol("BEL", sid="VZ-SID-Y")
    pm.add_leg("VZ", 5.0, 10, date(2012, 1, 5), contract_symbol="C1", live_symbol=a)
    pm.add_leg("BEL", 6.0, 10, date(2012, 5, 20), contract_symbol="C2", live_symbol=b)
    assert "VZ" not in pm.active_trades
    assert pm.get_trade("BEL").leg_count == 2


def test_close_leg_drops_sid_index(algo):
    pm = PositionManager(algo)
    sym = Symbol("AAPL", sid="AAPL-SID-2")
    leg = pm.add_leg(
        "AAPL", 5.0, 10, date(2024, 1, 1), contract_symbol="C", live_symbol=sym
    ).legs[0]
    pm.close_leg("AAPL", leg, exit_price=6.0, reason=config.EXIT_REASON_MANUAL)
    assert pm.has_position_for_sid("AAPL-SID-2") is False


def test_evict_orphan_pops_record_with_no_open_legs(algo):
    pm = PositionManager(algo)
    sym = Symbol("AAPL", sid="AAPL-SID-3")
    leg = pm.add_leg(
        "AAPL", 5.0, 10, date(2024, 1, 1), contract_symbol="C", live_symbol=sym
    ).legs[0]
    # Force-close the leg manually without going through close_leg's pop path.
    leg.status = "CLOSED"
    assert "AAPL" in pm.active_trades  # would orphan otherwise
    evicted = pm.evict_orphan("AAPL")
    assert evicted is not None
    assert "AAPL" not in pm.active_trades
    assert pm.has_position_for_sid("AAPL-SID-3") is False


def test_evict_orphan_refuses_when_legs_still_open(algo):
    pm = PositionManager(algo)
    pm.add_leg("AAPL", 5.0, 10, date(2024, 1, 1))
    assert pm.evict_orphan("AAPL") is None
    assert "AAPL" in pm.active_trades
