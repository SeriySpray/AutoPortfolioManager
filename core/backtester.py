"""
Walk-Forward 1-Month Leveraged Backtesting Engine for AutoPortfolioManager.
Simulates a monthly rebalancing strategy across S&P 500 equities using recent SSQ-Sharpe
and evaluates performance with 1x, 2x, and 3x margin leverage.
"""

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats

from core.quant_metrics import calculate_stock_quant_metrics


def filter_recent_candidates(
    prices_slice: pd.DataFrame,
    min_days: int = 60,
    max_recent_drawdown: float = 0.14,
    max_recent_vol: float = 0.65,
    rf_annual: float = 0.04,
) -> pd.DataFrame:
    """
    Evaluates candidate stocks over the recent lookback window (e.g. 63 days ~ 3 months).
    Applies strict risk and volatility filters required for safe leveraged investing (2x-3x).
    """
    candidates = []

    for ticker in prices_slice.columns:
        s = prices_slice[ticker].dropna()
        if len(s) < min_days:
            continue

        ret = s.pct_change().dropna()
        if len(ret) < min_days - 1:
            continue

        # Lookback cumulative return
        start_p = float(s.iloc[0])
        end_p = float(s.iloc[-1])
        if start_p <= 0 or end_p <= 0:
            continue

        tot_ret = (end_p / start_p) - 1.0

        # Lookback max drawdown
        cum_max = s.cummax()
        dd = (s - cum_max) / cum_max
        max_dd = float(dd.min())

        # Disqualify stocks that had excessive drops in recent months (lethal for 3x leverage)
        if abs(max_dd) > max_recent_drawdown:
            continue

        # Lookback annualized volatility
        ann_vol = float(ret.std(ddof=1)) * math.sqrt(252.0)
        if ann_vol > max_recent_vol or ann_vol <= 0.05:
            continue

        # Quick recent SSQ-Sharpe approximation on lookback
        daily_rf = (1.0 + rf_annual) ** (1.0 / 252.0) - 1.0
        downside_diff = np.minimum(0.0, ret.values - daily_rf)
        downside_dev = math.sqrt(float(np.mean(downside_diff ** 2))) * math.sqrt(252.0)
        downside_dev = max(1e-4, downside_dev)

        # Skewness and kurtosis
        skew = float(stats.skew(ret.values))
        kurt = float(stats.kurtosis(ret.values, fisher=False))
        tail_pen = max(0.1, 1.0 - (skew / 6.0) + ((kurt - 3.0) / 24.0))

        # Ulcer index on lookback
        ui = math.sqrt(float(np.mean(dd.values ** 2)))
        dd_pen = 1.0 + 2.0 * ui

        ann_excess_ret = (tot_ret * (252.0 / len(s))) - rf_annual
        recent_ssq = ann_excess_ret / (downside_dev * tail_pen * dd_pen)

        candidates.append({
            "ticker": ticker,
            "recent_return": tot_ret,
            "recent_vol": ann_vol,
            "recent_max_dd": max_dd,
            "recent_ssq": recent_ssq,
            "tail_pen": tail_pen,
            "ulcer_index": ui,
        })

    if not candidates:
        return pd.DataFrame()

    df = pd.DataFrame(candidates)
    # Sort by recent SSQ-Sharpe descending
    df = df.sort_values(by="recent_ssq", ascending=False).reset_index(drop=True)
    return df


def run_leveraged_monthly_backtest(
    prices_df: pd.DataFrame,
    metadata: Dict[str, Dict[str, str]],
    lookback_days: int = 63,       # ~3 months lookback to gauge current momentum & Sharpe
    holding_days: int = 21,        # ~1 month holding period
    top_n: int = 10,               # Pick top 10 stocks each month
    years_to_test: float = 5.0,    # Test over past 5 years
    borrow_rate_annual: float = 0.065, # 6.5% annual margin financing cost
    rf_annual: float = 0.04,
) -> Dict[str, Any]:
    """
    Executes a Walk-Forward monthly rebalancing simulation over historical daily prices.
    Tracks equity curves and risk statistics for 1x, 2x, and 3x leverage.
    """
    # 1. Determine timeline
    total_dates = len(prices_df.index)
    required_history = int(years_to_test * 252)
    start_idx = max(lookback_days + 10, total_dates - required_history)

    # List of rebalance dates (every `holding_days`)
    rebal_indices = list(range(start_idx, total_dates - holding_days, holding_days))

    if not rebal_indices:
        raise ValueError("Insufficient historical dates for the specified backtest parameters.")

    monthly_records = []
    ticker_pick_counts: Dict[str, List[float]] = {}

    # Equity curves initialized at 100.0
    equity_1x = [100.0]
    equity_2x = [100.0]
    equity_3x = [100.0]

    daily_borrow_rate = borrow_rate_annual / 252.0

    for idx in rebal_indices:
        rebal_date = prices_df.index[idx]
        fwd_end_idx = idx + holding_days
        fwd_end_date = prices_df.index[fwd_end_idx]

        # 2. Slice lookback window [idx - lookback_days, idx]
        lookback_slice = prices_df.iloc[idx - lookback_days : idx]

        # 3. Select top candidates
        candidates_df = filter_recent_candidates(
            lookback_slice,
            min_days=int(lookback_days * 0.9),
            max_recent_drawdown=0.14,
            max_recent_vol=0.60,
            rf_annual=rf_annual,
        )

        if candidates_df.empty or len(candidates_df) < 3:
            # Fallback if strict filter eliminated too many
            candidates_df = filter_recent_candidates(
                lookback_slice,
                min_days=int(lookback_days * 0.9),
                max_recent_drawdown=0.25,
                max_recent_vol=0.85,
                rf_annual=rf_annual,
            )

        top_picks = candidates_df.head(top_n)["ticker"].tolist()

        # 4. Forward simulation [idx, fwd_end_idx]
        forward_slice = prices_df[top_picks].iloc[idx : fwd_end_idx + 1]
        daily_returns_df = forward_slice.pct_change().dropna()

        # Equal-weighted daily portfolio return
        port_daily_ret = daily_returns_df.mean(axis=1)

        # Track daily equity with leverage
        current_eq_1x = equity_1x[-1]
        current_eq_2x = equity_2x[-1]
        current_eq_3x = equity_3x[-1]

        m1x = current_eq_1x
        m2x = current_eq_2x
        m3x = current_eq_3x

        intra_dd_1x = 0.0
        intra_dd_2x = 0.0
        intra_dd_3x = 0.0

        for r in port_daily_ret:
            # 1x Return
            m1x *= (1.0 + r)

            # 2x Return: 2 * return - 1 * borrow_cost
            r_2x = 2.0 * r - (1.0 * daily_borrow_rate)
            m2x *= (1.0 + r_2x)
            if m2x <= 0: m2x = 0.0

            # 3x Return: 3 * return - 2 * borrow_cost
            r_3x = 3.0 * r - (2.0 * daily_borrow_rate)
            m3x *= (1.0 + r_3x)
            if m3x <= 0: m3x = 0.0

            # Update intra-month drawdown
            intra_dd_1x = min(intra_dd_1x, (m1x - current_eq_1x) / current_eq_1x)
            intra_dd_2x = min(intra_dd_2x, (m2x - current_eq_2x) / current_eq_2x)
            intra_dd_3x = min(intra_dd_3x, (m3x - current_eq_3x) / current_eq_3x)

        # Record forward 1-month results
        month_ret_1x = (m1x / current_eq_1x) - 1.0
        month_ret_2x = (m2x / current_eq_2x) - 1.0 if current_eq_2x > 0 else -1.0
        month_ret_3x = (m3x / current_eq_3x) - 1.0 if current_eq_3x > 0 else -1.0

        equity_1x.append(m1x)
        equity_2x.append(m2x)
        equity_3x.append(m3x)

        # Track individual pick forward returns
        fwd_tot_per_ticker = (forward_slice.iloc[-1] / forward_slice.iloc[0]) - 1.0
        for t, val in fwd_tot_per_ticker.items():
            if t not in ticker_pick_counts:
                ticker_pick_counts[t] = []
            ticker_pick_counts[t].append(val)

        monthly_records.append({
            "start_date": rebal_date.strftime("%Y-%m-%d"),
            "end_date": fwd_end_date.strftime("%Y-%m-%d"),
            "picks": ", ".join(top_picks[:5]) + ("..." if len(top_picks) > 5 else ""),
            "picks_list": top_picks,
            "ret_1x": month_ret_1x,
            "ret_2x": month_ret_2x,
            "ret_3x": month_ret_3x,
            "intra_dd_2x": intra_dd_2x,
            "intra_dd_3x": intra_dd_3x,
        })

    # 5. Aggregate Performance Metrics for each leverage level
    def calc_tier_stats(returns: List[float], equity: List[float]) -> Dict[str, Any]:
        arr = np.array(returns)
        total_months = len(arr)
        pos_months = int(np.sum(arr > 0))
        win_rate = (pos_months / total_months) * 100.0 if total_months > 0 else 0.0

        cum_return = (equity[-1] / equity[0]) - 1.0
        years = (total_months * holding_days) / 252.0
        cagr = ((equity[-1] / equity[0]) ** (1.0 / max(0.1, years))) - 1.0 if equity[-1] > 0 else -1.0

        monthly_vol = float(np.std(arr, ddof=1)) if total_months > 1 else 0.0
        annual_vol = monthly_vol * math.sqrt(12.0)

        # Drawdown calculation on equity curve
        eq_arr = np.array(equity)
        peaks = np.maximum.accumulate(eq_arr)
        dds = (eq_arr - peaks) / peaks
        max_dd = float(np.min(dds))

        # Sharpe ratio on monthly returns
        mean_ret = float(np.mean(arr))
        monthly_rf = rf_annual / 12.0
        sharpe = ((mean_ret - monthly_rf) / monthly_vol) * math.sqrt(12.0) if monthly_vol > 0 else 0.0

        # Sortino
        downside = np.minimum(0.0, arr - monthly_rf)
        downside_std = math.sqrt(float(np.mean(downside ** 2)))
        sortino = ((mean_ret - monthly_rf) / downside_std) * math.sqrt(12.0) if downside_std > 0 else 0.0

        # Worst & Best month
        worst_m = float(np.min(arr)) * 100.0
        best_m = float(np.max(arr)) * 100.0

        return {
            "cum_return": cum_return * 100.0,
            "cagr": cagr * 100.0,
            "annual_vol": annual_vol * 100.0,
            "max_drawdown": max_dd * 100.0,
            "win_rate": win_rate,
            "sharpe": sharpe,
            "sortino": sortino,
            "worst_month": worst_m,
            "best_month": best_m,
        }

    rets_1x = [r["ret_1x"] for r in monthly_records]
    rets_2x = [r["ret_2x"] for r in monthly_records]
    rets_3x = [r["ret_3x"] for r in monthly_records]

    tier_1x = calc_tier_stats(rets_1x, equity_1x)
    tier_2x = calc_tier_stats(rets_2x, equity_2x)
    tier_3x = calc_tier_stats(rets_3x, equity_3x)

    # 6. Aggregate Stock-Level Statistics ("All-Stars")
    stock_stats = []
    for ticker, rets in ticker_pick_counts.items():
        if len(rets) >= 2:  # picked at least twice
            meta = metadata.get(ticker, {})
            name = meta.get("name", ticker)
            sector = meta.get("sector", "Unknown")
            arr_rets = np.array(rets)
            avg_ret = float(np.mean(arr_rets)) * 100.0
            win_r = float(np.mean(arr_rets > 0)) * 100.0
            worst_drop = float(np.min(arr_rets)) * 100.0
            best_gain = float(np.max(arr_rets)) * 100.0

            stock_stats.append({
                "ticker": ticker,
                "name": name,
                "sector": sector,
                "times_picked": len(rets),
                "avg_month_ret": avg_ret,
                "win_rate": win_r,
                "worst_month": worst_drop,
                "best_month": best_gain,
            })

    df_stock_stats = pd.DataFrame(stock_stats)
    if not df_stock_stats.empty:
        # Rank by score: high win rate + positive average return + mild worst drop
        df_stock_stats["score"] = (df_stock_stats["avg_month_ret"] * (df_stock_stats["win_rate"] / 100.0)) - (abs(df_stock_stats["worst_month"]) * 0.3)
        df_stock_stats = df_stock_stats.sort_values(by="score", ascending=False).reset_index(drop=True)

    return {
        "total_months": len(monthly_records),
        "start_date": monthly_records[0]["start_date"] if monthly_records else "",
        "end_date": monthly_records[-1]["end_date"] if monthly_records else "",
        "tier_1x": tier_1x,
        "tier_2x": tier_2x,
        "tier_3x": tier_3x,
        "monthly_records": monthly_records,
        "top_stocks": df_stock_stats,
    }


def get_current_leveraged_picks(
    prices_df: pd.DataFrame,
    metadata: Dict[str, Dict[str, str]],
    lookback_days: int = 63,
    top_n: int = 10,
    rf_annual: float = 0.04,
) -> pd.DataFrame:
    """
    Scans the most recent market data (up to today) and selects the optimal
    portfolio of stocks for the upcoming 1-month holding period with 2x-3x leverage.
    Includes calculated safety stop-loss levels and recommended leverage.
    """
    recent_slice = prices_df.iloc[-lookback_days:]
    candidates = filter_recent_candidates(
        recent_slice,
        min_days=int(lookback_days * 0.9),
        max_recent_drawdown=0.14,
        max_recent_vol=0.55,
        rf_annual=rf_annual,
    )

    if candidates.empty:
        candidates = filter_recent_candidates(
            recent_slice,
            min_days=int(lookback_days * 0.8),
            max_recent_drawdown=0.20,
            max_recent_vol=0.75,
            rf_annual=rf_annual,
        )

    top_picks = candidates.head(top_n).copy()

    records = []
    for _, row in top_picks.iterrows():
        t = row["ticker"]
        meta = metadata.get(t, {})
        ann_vol = row["recent_vol"]
        max_dd = row["recent_max_dd"]

        # Recommendation: 3x if low volatility and very shallow drawdown, else 2x
        if ann_vol <= 0.28 and abs(max_dd) <= 0.08:
            rec_leverage = "3x (Висока стабільність)"
            stop_loss = 6.0  # 6% stop loss on stock protects a 3x position from losing >18%
        else:
            rec_leverage = "2x (Помірний ризик)"
            stop_loss = 8.5  # 8.5% stop loss protects 2x position from losing >17%

        records.append({
            "ticker": t,
            "name": meta.get("name", t),
            "sector": meta.get("sector", "Unknown"),
            "recent_3m_ret": row["recent_return"] * 100.0,
            "recent_vol": ann_vol * 100.0,
            "recent_max_dd": max_dd * 100.0,
            "recent_ssq": row["recent_ssq"],
            "rec_leverage": rec_leverage,
            "stop_loss_pct": stop_loss,
        })

    return pd.DataFrame(records)
