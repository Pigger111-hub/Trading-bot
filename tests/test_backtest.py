"""Development-only SYNTHETIC fixtures; no real market data or approvals."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import trading_lab.backtest as engine


def test_synthetic_long_only_next_open_fractional_execution(synthetic_frame):
    result = engine.run_backtest(synthetic_frame, 3, 8, 0.001, 0.002)
    assert result["trades"] > 0
    assert result["trades"] == len(result["trade_ledger"])
    assert result["metadata"]["trade_on_close"] is False
    assert result["metadata"]["fractional_unit"] == 1e-8
    assert result["metadata"]["margin"] == 1
    for trade in result["trade_ledger"]:
        entry = synthetic_frame.index.get_loc(pd.Timestamp(trade["entry_time"]))
        assert trade["side"] == "long"
        assert 0 < trade["size"] < 1  # BTC, not internal satoshi integer units.
        assert trade["entry_price"] == pytest.approx(synthetic_frame.Open.iloc[entry] * 1.002)
        assert trade["entry_signal_time"] == synthetic_frame.index[entry - 1].isoformat()
        exit_bar = synthetic_frame.index.get_loc(pd.Timestamp(trade["exit_time"]))
        assert trade["exit_price"] == pytest.approx(synthetic_frame.Open.iloc[exit_bar])
        assert trade["exit_signal_time"] == synthetic_frame.index[exit_bar - 1].isoformat()
    assert all(point["position_size"] >= 0 for point in result["equity_curve"])
    assert all(point["spot_cash"] >= -1e-8 for point in result["equity_curve"])
    assert 0 <= result["exposure_pct"] <= 100
    assert result["max_drawdown_pct"] <= 0
    assert result == engine.run_backtest(synthetic_frame, 3, 8, 0.001, 0.002)
    json.dumps(result, allow_nan=False)


@pytest.fixture
def synthetic_frame():
    """Artificial BTC-scale oscillations, NOT historical market prices."""
    x = np.arange(180)
    close = 30_000 + 2_000 * np.sin(x / 5) + x * 8
    opened = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"Open": opened, "High": np.maximum(opened, close) + 20,
                         "Low": np.minimum(opened, close) - 20, "Close": close,
                         "Volume": np.ones(len(x))},
                        index=pd.date_range("2020-01-01", periods=len(x), freq="h", tz="UTC"))


def test_synthetic_terminal_position_is_marked_not_fictitiously_realized():
    # Deliberately artificial prices, rising after a trough; leaves one open long.
    close = np.array([100, 99, 98, 97, 96, 97, 99, 102, 106, 110, 115, 120]) * 100.0
    opened = np.r_[close[0], close[:-1]]
    frame = pd.DataFrame({"Open": opened, "High": np.maximum(opened, close),
                          "Low": np.minimum(opened, close), "Close": close, "Volume": 1.0},
                         index=pd.date_range("2020-01-01", periods=len(close), freq="h", tz="UTC"))
    result = engine.run_backtest(frame, 2, 3, 0.001, 0.002)
    assert result["trades"] == 0
    assert result["realized_pnl"] == 0
    assert len(result["terminal_positions"]) == 1
    mark = result["terminal_positions"][0]
    assert mark["status"] == "terminal_mark_not_realized"
    assert mark["mark_price"] == close[-1]
    assert mark["mark_time"] == frame.index[-1].isoformat()
    assert mark["entry_commission"] == pytest.approx(mark["size"] * mark["entry_price"] * 0.001)
    assert mark["gross_unrealized_pnl"] == pytest.approx(mark["size"] * (close[-1] - mark["entry_price"]))
    assert mark["net_mark_pnl"] == pytest.approx(mark["gross_unrealized_pnl"] - mark["entry_commission"])
    assert result["terminal_equity"] == pytest.approx(10_000 + mark["net_mark_pnl"])
    assert result["return_pct"] == pytest.approx(mark["net_mark_pnl"] / 100)
    assert mark["size"] * mark["entry_price"] + mark["entry_commission"] <= 1000 + 1e-6
    assert result["exposure_pct"] > 0  # Includes open exposure, not just library closed trades.
    assert result["metadata"]["terminal_exit_commission_applied"] is False
    json.dumps(result, allow_nan=False)


def test_synthetic_baselines_have_same_window_costs_and_explicit_marks(synthetic_frame):
    result = engine.run_backtest(synthetic_frame, 3, 8, 0.002, 0.003)
    baseline = result["baselines"]
    assert baseline["cash"]["terminal_equity"] == 10_000
    assert baseline["cash"]["return_pct"] == 0
    assert baseline["cash"]["exposure_pct"] == 0
    assert baseline["cash"]["trades"] == 0
    held = baseline["buy_and_hold"]
    # Decision at the first test candle close; buy at the following open,
    # 100%-cash comparison (not risk matched), satoshi-rounded and entry-fee aware.
    entry = synthetic_frame.Open.iloc[9] * 1.003
    units = np.floor(10_000 / (entry * 1.002) / 1e-8) * 1e-8
    expected_cash = 10_000 - units * entry * 1.002
    expected_equity = expected_cash + units * synthetic_frame.Close.iloc[-1]
    assert held["entry_time"] == synthetic_frame.index[9].isoformat()
    assert held["size"] == pytest.approx(units)
    assert held["terminal_equity"] == pytest.approx(expected_equity)
    assert held["trades"] == 0  # No fabricated realized exit.
    assert held["realized_pnl"] == 0
    assert held["status"] == "terminal_mark_not_realized"
    assert held["allocation_fraction"] == 1.0
    assert held["exit_commission_applied"] is False
    assert held["return_pct"] == pytest.approx((expected_equity / 10_000 - 1) * 100)
    json.dumps(result, allow_nan=False)


def test_synthetic_walk_forward_fixed_folds_warmup_and_no_boundary_trades(synthetic_frame):
    report = engine.walk_forward(synthetic_frame, 3, 8, 0.001, 0.001)
    assert report["split_policy"] == "initial_half_then_three_chronological_tests"
    assert report["parameter_selection"] == "none"
    assert report["final_holdout_fold"] == 2
    assert len(report["folds"]) == 3
    previous_end = None
    for number, fold in enumerate(report["folds"]):
        start = 90 + number * 30
        assert fold["test_start"] == synthetic_frame.index[start].isoformat()
        assert fold["test_end"] == synthetic_frame.index[start + 29].isoformat()
        assert fold["warmup_start"] == synthetic_frame.index[start - 9].isoformat()
        assert fold["test_bars"] == 30
        result = fold["result"]
        assert result["metadata"]["cash"] == 10000
        assert result["metadata"]["fast"] == 3
        assert result["metadata"]["slow"] == 8
        assert result["metadata"]["evaluation_start"] == fold["test_start"]
        if previous_end is not None:
            assert pd.Timestamp(previous_end) < pd.Timestamp(fold["test_start"])
        for signal in result["signals"]:
            assert signal["time"] >= fold["test_start"]
            assert signal["execution_time"] > fold["test_start"]
        for trade in result["trade_ledger"] + result["terminal_positions"]:
            assert trade["entry_time"] > fold["test_start"]
        assert all(point["time"] >= fold["test_start"] for point in result["equity_curve"])
        previous_end = fold["test_end"]
    assert report == engine.walk_forward(synthetic_frame, 3, 8, 0.001, 0.001)
    json.dumps(report, allow_nan=False)


def test_synthetic_baseline_includes_equal_initial_allocation(synthetic_frame):
    result = engine.run_backtest(synthetic_frame, 3, 8, 0.002, 0.003, position_fraction=0.05)
    held = result['baselines']['buy_and_hold_equal_allocation']
    assert held['allocation_fraction'] == 0.05
    assert held['size'] * held['entry_price'] + held['entry_commission'] <= 500 + 1e-6
    assert held['spot_cash'] >= 9500 - 1e-6


def test_engine_hash_covers_entire_module_bytes():
    assert engine.engine_hash() == hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest()
    assert engine.engine_hash() == engine.engine_hash()


@pytest.mark.parametrize("overrides", [
    {"fast": True}, {"fast": 2.0}, {"fast": 0}, {"fast": 8, "slow": 8},
    {"slow": False}, {"slow": 1000}, {"commission": float("nan")},
    {"commission": float("inf")}, {"commission": -0.01}, {"commission": True},
    {"commission": 0.1}, {"spread": -0.1}, {"spread": float("inf")},
    {"spread": 1.0}, {"cash": 0}, {"cash": True}, {"cash": float("inf")},
    {"position_fraction": 0}, {"position_fraction": 0.10001},
    {"position_fraction": True}, {"position_fraction": float("nan")},
])
def test_invalid_parameters_rejected(synthetic_frame, overrides):
    args = dict(fast=3, slow=8, commission=0.001, spread=0.001)
    args.update(overrides)
    with pytest.raises(ValueError):
        engine.run_backtest(synthetic_frame, **args)


@pytest.mark.parametrize("defect", ["naive", "unsorted", "duplicate", "nan", "negative",
                                   "inconsistent", "volume", "bool", "short", "missing"])
def test_invalid_frames_rejected(synthetic_frame, defect):
    frame = synthetic_frame.copy()
    if defect == "naive":
        frame.index = frame.index.tz_localize(None)
    elif defect == "unsorted":
        frame = frame.iloc[::-1]
    elif defect == "duplicate":
        frame.index = pd.DatetimeIndex([frame.index[0]] * len(frame))
    elif defect == "nan":
        frame.iloc[4, 0] = np.nan
    elif defect == "negative":
        frame.iloc[4, 0] = -1
    elif defect == "inconsistent":
        frame.iloc[4, 1] = 1
    elif defect == "volume":
        frame.iloc[4, 4] = -1
    elif defect == "bool":
        frame["Volume"] = True
    elif defect == "short":
        frame = frame.iloc[:9]
    elif defect == "missing":
        frame = frame.drop(columns="Open")
    with pytest.raises(ValueError):
        engine.run_backtest(frame, 3, 8, 0.001, 0.001)


def test_synthetic_future_perturbation_preserves_earlier_signals_trades_and_marks(synthetic_frame):
    changed = synthetic_frame.copy(deep=True)
    changed.loc[changed.index[110]:, ["Open", "High", "Low", "Close"]] *= 2
    original = engine.run_backtest(synthetic_frame, 3, 8, 0.001, 0.002)
    perturbed = engine.run_backtest(changed, 3, 8, 0.001, 0.002)
    cutoff = synthetic_frame.index[110].isoformat()
    for key, time_key in (("signals", "time"), ("trade_ledger", "exit_time"), ("equity_curve", "time")):
        assert [item for item in original[key] if item[time_key] < cutoff] == [
            item for item in perturbed[key] if item[time_key] < cutoff]
    fast, slow = synthetic_frame.Close.rolling(3).mean(), synthetic_frame.Close.rolling(8).mean()
    for signal in original["signals"]:
        bar = synthetic_frame.index.get_loc(pd.Timestamp(signal["time"]))
        if signal["action"] == "buy":
            assert fast.iloc[bar - 1] <= slow.iloc[bar - 1] and fast.iloc[bar] > slow.iloc[bar]
        else:
            assert fast.iloc[bar - 1] >= slow.iloc[bar - 1] and fast.iloc[bar] < slow.iloc[bar]


def test_synthetic_holdout_perturbation_cannot_change_earlier_folds(synthetic_frame):
    changed = synthetic_frame.copy(deep=True)
    changed.loc[changed.index[150]:, ["Open", "High", "Low", "Close"]] *= 3
    original = engine.walk_forward(synthetic_frame, 3, 8, 0.001, 0.002)
    perturbed = engine.walk_forward(changed, 3, 8, 0.001, 0.002)
    assert original["folds"][:2] == perturbed["folds"][:2]


def test_synthetic_commission_and_spread_reduce_returns(synthetic_frame):
    free = engine.run_backtest(synthetic_frame, 3, 8, 0, 0)
    fee = engine.run_backtest(synthetic_frame, 3, 8, 0.005, 0)
    spread = engine.run_backtest(synthetic_frame, 3, 8, 0, 0.005)
    assert fee["trades"] == spread["trades"] == free["trades"] > 0
    assert fee["return_pct"] < free["return_pct"]
    assert spread["return_pct"] < free["return_pct"]
    for trade in fee["trade_ledger"]:
        assert trade["commission"] == pytest.approx(
            trade["size"] * (trade["entry_price"] + trade["exit_price"]) * 0.005)
        assert trade["net_pnl"] == pytest.approx(
            trade["size"] * (trade["exit_price"] - trade["entry_price"]) - trade["commission"])
    assert fee["terminal_equity"] == pytest.approx(
        10000 + fee["realized_pnl"] + sum(t["net_mark_pnl"] for t in fee["terminal_positions"]))


@pytest.mark.parametrize("length", [15, 19, 25, 179])
def test_synthetic_walk_forward_uneven_splits_cover_all_reserved_rows(synthetic_frame, length):
    frame = synthetic_frame.iloc[:length]
    result = engine.walk_forward(frame, 2, 3, 0, 0)
    first = max(length // 2, 4)
    covered = [point["time"] for fold in result["folds"] for point in fold["result"]["equity_curve"]]
    assert covered == [time.isoformat() for time in frame.index[first:]]


def test_synthetic_walk_forward_rejects_insufficient_test_rows(synthetic_frame):
    with pytest.raises(ValueError, match="three tests"):
        engine.walk_forward(synthetic_frame.iloc[:14], 3, 8, 0, 0)


def test_synthetic_inputs_unchanged_and_numpy_parameters_serialize(synthetic_frame):
    before = synthetic_frame.copy(deep=True)
    result = engine.run_backtest(synthetic_frame, np.int64(3), np.int64(8), np.float64(0.001),
                                 np.float64(0.002), cash=np.int64(10000))
    pd.testing.assert_frame_equal(before, synthetic_frame)
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("commission,spread", [(0, 0), (0.001, 0.002), (0.09, 0.9)])
def test_synthetic_entry_allocation_includes_spread_adjusted_commission(synthetic_frame, commission, spread):
    result = engine.run_backtest(synthetic_frame, 3, 8, commission, spread)
    by_time = {point["time"]: point for point in result["equity_curve"]}
    for trade in result["trade_ledger"] + result["terminal_positions"]:
        equity_before = by_time[trade["entry_signal_time"]]["equity"]
        entry_outlay = trade["size"] * trade["entry_price"] * (1 + commission)
        assert 0 < entry_outlay <= equity_before * 0.1 + 1e-6
    assert all(point["spot_cash"] >= -1e-6 for point in result["equity_curve"])


def test_synthetic_fractional_scaling_rejects_overflow(synthetic_frame):
    frame = synthetic_frame.copy()
    frame["Volume"] = 1e308
    with pytest.raises(ValueError, match="fractional"):
        engine.run_backtest(frame, 3, 8, 0, 0)


def test_synthetic_terminal_overflow_is_rejected_not_serialized(synthetic_frame):
    # Valid finite OHLC, but enormous price shock makes held mark overflow.
    frame = synthetic_frame.copy()
    frame.loc[frame.index[-1], ["Open", "High", "Low", "Close"]] = 1e308
    with pytest.raises(ValueError, match="finite|overflow"):
        engine.run_backtest(frame, 3, 8, 0, 0, cash=1e8)


def test_synthetic_flat_no_trade_diagnostics_are_finite(synthetic_frame):
    frame = synthetic_frame.copy()
    frame.loc[:, ["Open", "High", "Low", "Close"]] = 30000.0
    result = engine.run_backtest(frame, 3, 8, 0, 0)
    assert result["return_pct"] == result["max_drawdown_pct"] == result["exposure_pct"] == 0
    assert result["trades"] == 0
    assert result["diagnostics"]["open_positions"] == 0
    assert result["diagnostics"]["completed_round_trips"] == 0
    assert result["diagnostics"]["evaluation_bars"] == 172
    assert result["diagnostics"]["signals"] == 0
    json.dumps(result, allow_nan=False)
