"""Fixed native research engine, not a sandbox or an approval/budget boundary.

Only the parent approval runner may authorize a research batch. This module does
not load user strategies, execute arbitrary code, run continuously, or trade live.
"""
from hashlib import sha256
import json
from pathlib import Path
from numbers import Integral, Real
import warnings

from backtesting import Strategy
from backtesting.lib import FractionalBacktest

import numpy as np
import pandas as pd


_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
FRACTIONAL_UNIT = 1e-8  # One BTC satoshi; input prices remain quote-currency/BTC.


def _validate(frame, fast, slow, commission, spread, cash, position_fraction):
    for name, value in (("fast", fast), ("slow", slow)):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < 1:
            raise ValueError(f"{name} must be a positive integer (not bool)")
    if fast >= slow:
        raise ValueError("fast must be less than slow")
    for name, value, lower, upper in (
        ("commission", commission, 0, 0.1), ("spread", spread, 0, 1),
        ("cash", cash, 0, None), ("position_fraction", position_fraction, 0, 0.1),
    ):
        if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
                or not np.isfinite(value) or value < lower):
            raise ValueError(f"invalid finite numeric {name}")
        if name in ("cash", "position_fraction") and value == 0:
            raise ValueError(f"{name} must be positive")
        if upper is not None and (value > upper or (name != "position_fraction" and value == upper)):
            raise ValueError(f"{name} exceeds supported range")
    if not isinstance(frame, pd.DataFrame) or not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("frame must have a UTC DatetimeIndex")
    if (str(frame.index.tz) != "UTC" or frame.index.hasnans or not frame.index.is_unique
            or not frame.index.is_monotonic_increasing):
        raise ValueError("timestamps must be unique, increasing and UTC")
    if not frame.columns.is_unique or not set(_COLUMNS).issubset(frame.columns):
        raise ValueError("unique OHLCV columns required")
    if len(frame) < slow + 2:
        raise ValueError("need at least slow + 2 candles for warmup and next-open execution")
    selected = frame[_COLUMNS]
    if any(not pd.api.types.is_numeric_dtype(dtype) or pd.api.types.is_bool_dtype(dtype)
           or pd.api.types.is_complex_dtype(dtype) for dtype in selected.dtypes):
        raise ValueError("OHLCV must be real numeric, not bool")
    values = selected.to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError("finite positive prices and nonnegative volume required")
    o, h, low, c = values[:, :4].T
    if ((h < np.maximum(o, c)) | (low > np.minimum(o, c)) | (h < low)).any():
        raise ValueError("inconsistent OHLC envelope")
    # The broker rescales prices/volume. Reject unrepresentable scaling and
    # conservative worst-case account marks before entering numerical internals.
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            scaled_prices = values[:, :4] * FRACTIONAL_UNIT
            scaled_volume = values[:, 4] / FRACTIONAL_UNIT
            possible_units = float(cash) / scaled_prices.min()
            possible_mark = float(cash) * (values[:, :4].max() / values[:, :4].min())
        if (not np.isfinite(scaled_prices).all() or not np.isfinite(scaled_volume).all()
                or (scaled_prices <= 0).any() or not np.isfinite(possible_units)
                or not np.isfinite(possible_mark)):
            raise ValueError("fractional scaling or finite account marks overflow")
    except (FloatingPointError, OverflowError) as exc:
        raise ValueError("fractional scaling or finite account marks overflow") from exc
    return selected.astype(float).copy()


def _sma(values, window):
    """Trailing-only arithmetic mean, with no centered windows or backfilling."""
    return pd.Series(values).rolling(window, min_periods=window).mean().to_numpy()


class _SmaCross(Strategy):
    fast = 3
    slow = 8
    position_fraction = 0.1
    order_fraction = 0.1
    test_start = 0

    def init(self):
        self.fast_line = self.I(_sma, self.data.Close, self.fast, overlay=False)
        self.slow_line = self.I(_sma, self.data.Close, self.slow, overlay=False)
        self.signals = []
        self.curve = []
        self._timestamps = self.data.index.copy()

    def next(self):
        bar = len(self.data) - 1
        if bar < self.test_start:
            return  # Warmup never places an order or changes the starting account.
        size = float(self.position.size * FRACTIONAL_UNIT)
        mark = float(self.data.Close[-1] / FRACTIONAL_UNIT)
        self.curve.append({"time": self.data.index[-1].isoformat(),
                           "equity": float(self.equity), "position_size": size,
                           "spot_cash": float(self.equity - size * mark)})
        if bar == len(self._timestamps) - 1:
            return  # No imaginary execution beyond the supplied batch.
        action = None
        if self.fast_line[-2] <= self.slow_line[-2] and self.fast_line[-1] > self.slow_line[-1]:
            if not self.position:
                self.buy(size=self.order_fraction)
                action = "buy"
        elif self.fast_line[-2] >= self.slow_line[-2] and self.fast_line[-1] < self.slow_line[-1]:
            if self.position:
                self.position.close()
                action = "close_long"
        if action:
            self.signals.append({"time": self.data.index[-1].isoformat(), "action": action,
                                 "execution_time": self._timestamps[bar + 1].isoformat()})


def _metrics(curve, cash, trades):
    equities = np.r_[cash, [p["equity"] for p in curve]]
    if not np.isfinite(equities).all():
        raise ValueError("non-finite terminal/equity mark; refusing JSON NaN/Infinity")
    drawdowns = equities / np.maximum.accumulate(equities) - 1
    return {"return_pct": float((equities[-1] / cash - 1) * 100),
            "max_drawdown_pct": float(drawdowns.min() * 100), "trades": int(trades),
            "exposure_pct": float(100 * sum(p["position_size"] > 0 for p in curve) / len(curve))}


def _baselines(frame, test_start, cash, commission, spread, allocation_fraction=1.0):
    """Cash and 100%-cash buy/hold, not risk-matched to the 10%-cap strategy.

    Both share the evaluation window. Buy/hold decides at first test close and
    buys at the next open, pays identical entry spread/fee, rounds down satoshis,
    and marks at the last close. Neither assumes a terminal sell or exit fee.
    'trades' counts completed round trips (zero for an unliquidated holding).
    """
    entry_bar = test_start + 1
    price = float(frame.Open.iloc[entry_bar] * (1 + spread))
    size = float(np.floor(cash * allocation_fraction / (price * (1 + commission)) / FRACTIONAL_UNIT)
                 * FRACTIONAL_UNIT)
    fee = size * price * commission
    remaining = cash - size * price - fee
    held_curve = []
    cash_curve = []
    for bar in range(test_start, len(frame)):
        time = frame.index[bar].isoformat()
        invested = bar >= entry_bar
        held_curve.append({"time": time, "position_size": size if invested else 0.0,
                           "equity": float(remaining + size * frame.Close.iloc[bar]) if invested else float(cash)})
        cash_curve.append({"time": time, "position_size": 0.0, "equity": float(cash)})
    held = _metrics(held_curve, cash, 0)
    held.update({"terminal_equity": held_curve[-1]["equity"], "realized_pnl": 0.0,
                 "entry_time": frame.index[entry_bar].isoformat(), "entry_price": price,
                 "entry_commission": float(fee), "size": size, "spot_cash": float(remaining),
                 "allocation_fraction": float(allocation_fraction), "status": "terminal_mark_not_realized",
                 "mark_time": frame.index[-1].isoformat(), "mark_price": float(frame.Close.iloc[-1]),
                 "net_mark_pnl": float(held_curve[-1]["equity"] - cash),
                 "exit_commission_applied": False})
    idle = _metrics(cash_curve, cash, 0)
    idle.update({"terminal_equity": float(cash), "realized_pnl": 0.0, "status": "cash"})
    return {"cash": idle, "buy_and_hold": held}


def _run(frame, fast, slow, commission, spread, cash, position_fraction, test_start):
    backtest = FractionalBacktest(frame, _SmaCross, cash=float(cash), commission=float(commission),
                                 spread=float(spread), margin=1, trade_on_close=False,
                                 hedging=False, exclusive_orders=True, finalize_trades=False,
                                 fractional_unit=FRACTIONAL_UNIT)
    with warnings.catch_warnings():
        # Intentionally mark open positions instead of the library's synthetic
        # last-open liquidation. All other broker warnings remain visible.
        warnings.filterwarnings("ignore", message="Some trades remain open at the end of backtest.*",
                                category=UserWarning)
        # 0.6.6 sizes fractions using open*(1+spread+commission), but charges
        # commission on spread-adjusted entry. Correct the cross-term so the
        # actual notional PLUS entry commission never exceeds the stated cap.
        order_fraction = position_fraction * (1 + spread + commission) / ((1 + spread) * (1 + commission))
        stats = backtest.run(fast=int(fast), slow=int(slow), position_fraction=float(position_fraction),
                             order_fraction=float(order_fraction), test_start=int(test_start))
    strategy = stats["_strategy"]
    ledger = []
    for _, trade in stats["_trades"].iterrows():
        entry, exit_bar = int(trade.EntryBar), int(trade.ExitBar)
        ledger.append({"side": "long", "size": float(trade.Size),
                       "entry_time": frame.index[entry].isoformat(),
                       "exit_time": frame.index[exit_bar].isoformat(),
                       "entry_signal_time": frame.index[entry - 1].isoformat(),
                       "exit_signal_time": frame.index[exit_bar - 1].isoformat(),
                       "entry_price": float(trade.EntryPrice), "exit_price": float(trade.ExitPrice),
                       "commission": float(trade.Commission), "net_pnl": float(trade.PnL),
                       "status": "realized"})
    marks = []
    for trade in strategy.trades:
        size = float(trade.size * FRACTIONAL_UNIT)
        entry_price = float(trade.entry_price / FRACTIONAL_UNIT)
        entry_fee = size * entry_price * commission
        gross = size * (float(frame.Close.iloc[-1]) - entry_price)
        marks.append({"side": "long", "status": "terminal_mark_not_realized",
                      "size": size, "entry_time": frame.index[trade.entry_bar].isoformat(),
                      "entry_signal_time": frame.index[trade.entry_bar - 1].isoformat(),
                      "entry_price": entry_price, "entry_commission": float(entry_fee),
                      "mark_time": frame.index[-1].isoformat(), "mark_price": float(frame.Close.iloc[-1]),
                      "gross_unrealized_pnl": float(gross), "net_mark_pnl": float(gross - entry_fee)})
    result = _metrics(strategy.curve, cash, len(ledger))
    result.update({"baselines": _baselines(frame, test_start, cash, commission, spread),
                   "diagnostics": {"open_positions": len(marks), "completed_round_trips": len(ledger),
                                   "evaluation_bars": len(strategy.curve), "signals": len(strategy.signals)},
                   "terminal_positions": marks,
                   "realized_pnl": float(sum(t["net_pnl"] for t in ledger)),
                   "terminal_equity": float(strategy.curve[-1]["equity"]),
                   "trade_ledger": ledger, "signals": strategy.signals, "equity_curve": strategy.curve,
                   "metadata": {"engine_hash": engine_hash(), "strategy": "native_sma_crossover_v1",
                                "trade_on_close": False, "margin": 1, "fractional_unit": FRACTIONAL_UNIT,
                                "fast": int(fast), "slow": int(slow), "commission": float(commission),
                                "spread": float(spread), "cash": float(cash),
                                "position_fraction": float(position_fraction),
                                "data_start": frame.index[0].isoformat(),
                                "evaluation_start": frame.index[test_start].isoformat(),
                                "data_end": frame.index[-1].isoformat(),
                                "bars": len(frame), "warmup_bars": int(test_start),
                                "timing": "closed-bar signal; following candle open fill",
                                "terminal_exit_commission_applied": False,
                                "terminal_policy": "mark_to_final_close_no_forced_fill"}})
    result['baselines']['buy_and_hold_equal_allocation'] = _baselines(
        frame, test_start, cash, commission, spread, position_fraction)['buy_and_hold']
    # Equal initial allocation is not continuously exposure/risk matched.
    # All timestamps/scalars are converted at the boundary. Refuse to emit a
    # superficially successful report with non-finite ledger/terminal metrics.
    try:
        json.dumps(result, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("result is not finite JSON-safe data") from exc
    return result


def run_backtest(frame, fast: int, slow: int, commission: float, spread: float,
                 cash: float = 10000, position_fraction: float = 0.1) -> dict:
    """Run the fixed, long-only SMA crossover, using BTC satoshi-sized units.

    Inputs are closed candles indexed by UTC candle identifiers (the caller must
    establish their provenance/completeness). At candle i close, trailing SMAs
    cross from <= to > to buy, or >= to < to close. Fill is candle i+1 open.
    The first slow bars warm up indicators, never trades. Positions use at most
    position_fraction of available equity at entry, including entry costs, with
    margin=1 and no pyramiding, borrowing, shorts, funding, or partial fills.
    Price appreciation may subsequently increase the exposure above 10%.
    Spread is the library's one-sided long entry adjustment; commission applies
    at both entry and actual exit. No slippage/market impact beyond that spread.
    No final-bar order is submitted because no following open is available.

    'trades' counts realized completed round trips only; trade_ledger contains
    their net realized PnL/fees. Open positions are separate terminal_positions,
    marked at the final supplied close, net of paid entry commission but without
    a fictitious exit, spread or exit fee. terminal_equity and return_pct include
    these marks, not just realized_pnl. max_drawdown_pct is a nonpositive number
    measured against running marked-equity peaks (including initial cash).
    exposure_pct counts evaluation candles with a nonzero long position at
    close, including terminal open exposure. Intrabar drawdown is not measured.
    Baselines are idle cash and cost-aware 100%-cash buy/hold over the same
    evaluation window; the latter is intentionally NOT risk/exposure matched.
    All prices/ledger sizes are quote-currency per BTC/BTC, not satoshi-scaled.
    Unrepresentable numerical scaling/marks fail rather than emit NaN/Infinity.

    Output timing is candle-derived, not nondeterministic wall-clock runtime.
    Approval, budget, data leakage outside this module, and risk policy belong
    to the parent runner; this module is not a security sandbox.
    """
    data = _validate(frame, fast, slow, commission, spread, cash, position_fraction)
    return _run(data, fast, slow, commission, spread, cash, position_fraction, int(slow))


def walk_forward(frame, fast, slow, commission, spread, position_fraction=0.1) -> dict:
    """Three chronological independent out-of-sample windows; no optimization.

    Reserve floor(n/2) rows (or slow+1 if larger) as initial history. Split the
    remaining rows into three contiguous tests using numpy.array_split (earlier
    folds get remainder rows). Each needs at least two bars for a decision/fill.
    Each test uses exactly slow+1 preceding candles solely for trailing SMA
    warmup and starts flat with 10,000 cash. Signals may begin at its first close;
    no pre-boundary orders, carried positions, or training-window PnL survive.
    The third fold is explicitly the final holdout. Fixed caller parameters are
    never selected using any fold, especially not the holdout. This is rolling
    evaluation, not a claim that repeated human selection cannot overfit it.
    Folds are not compounded or pooled into misleading contiguous-trading PnL.
    Windows are fixed by row counts, not durations; gaps must be vetted upstream.
    """
    data = _validate(frame, fast, slow, commission, spread, 10000, position_fraction)
    first = max(len(data) // 2, int(slow) + 1)
    if len(data) - first < 6:
        raise ValueError("walk_forward needs history and three tests of at least two bars each")
    windows = np.array_split(np.arange(first, len(data)), 3)
    folds = []
    for number, window in enumerate(windows):
        start, end = int(window[0]), int(window[-1]) + 1
        warmup_start = start - (int(slow) + 1)
        sample = data.iloc[warmup_start:end].copy()
        folds.append({"fold": number, "role": "final_holdout" if number == 2 else "evaluation",
                      "test_start": data.index[start].isoformat(),
                      "test_end": data.index[end - 1].isoformat(), "test_bars": end - start,
                      "warmup_start": data.index[warmup_start].isoformat(),
                      "result": _run(sample, fast, slow, commission, spread, 10000,
                                     position_fraction, int(slow) + 1)})
    return {"split_policy": "initial_half_then_three_chronological_tests",
            "parameter_selection": "none", "final_holdout_fold": 2,
            "independent_accounts": True, "folds": folds}


def engine_hash() -> str:
    """SHA256 of this entire source file, including comments and whitespace.

    Identifies this file only, not dependencies or data. The parent must verify
    approved inputs and environment separately; this is not runtime isolation.
    """
    return sha256(Path(__file__).read_bytes()).hexdigest()
