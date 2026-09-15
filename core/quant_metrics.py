"""
Quantitative Metrics Engine for AutoPortfolioManager.
Calculates Classic Sharpe, Sortino, and the Single-Stock Quant Sharpe (SSQ-Sharpe)
using:
1. Downside Deviation
2. Andrew Lo's Autocorrelation Correction (Lo, 2002)
3. Cornish-Fisher Expansion Tail Penalty (Skewness & Kurtosis)
4. Ulcer Index Drawdown Penalty
"""

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats


def calculate_stock_quant_metrics(
    series: pd.Series,
    rf_annual: float = 0.04,
    min_days: int = 252,
) -> Optional[Dict[str, Any]]:
    """
    Computes all standard and adapted risk-adjusted metrics for a single stock price series.

    :param series: Pandas Series of historical daily adjusted closing prices.
    :param rf_annual: Annual risk-free rate (default: 4.0%).
    :param min_days: Minimum valid daily prices required (default: 252 days = 1 year).
    :return: Dictionary with computed quant metrics, or None if insufficient data.
    """
    clean_series = series.dropna().astype(float)
    clean_series = clean_series[clean_series > 0]

    if len(clean_series) < min_days:
        return None

    # 1. Daily Returns & Excess Returns
    daily_returns = clean_series.pct_change().dropna()
    total_days = len(daily_returns)
    if total_days < min_days:
        return None

    total_years = total_days / 252.0
    daily_rf = (1.0 + rf_annual) ** (1.0 / 252.0) - 1.0
    excess_returns = daily_returns - daily_rf

    # 2. Return Dynamics (CAGR and Annual Excess Return)
    start_price = float(clean_series.iloc[0])
    end_price = float(clean_series.iloc[-1])
    cagr = (end_price / start_price) ** (1.0 / total_years) - 1.0
    annual_excess_return = cagr - rf_annual

    # 3. Total Annualized Volatility
    daily_vol = float(daily_returns.std(ddof=1))
    annual_vol = daily_vol * math.sqrt(252.0)
    if annual_vol <= 1e-6:
        return None

    # 4. Downside Deviation (Sortino Component)
    downside_excess = np.minimum(0.0, excess_returns.values)
    downside_var = float(np.mean(downside_excess ** 2))
    downside_dev = math.sqrt(downside_var) * math.sqrt(252.0)
    # Floor to avoid division by zero
    downside_dev = max(1e-4, downside_dev)

    # 5. Andrew Lo's Autocorrelation Correction (Lo, 2002)
    # Calculate autocorrelations for lags 1 to 5
    autocorr_sum = 0.0
    lags = [1, 2, 3, 4, 5]
    autocorr_values = []
    for k in lags:
        if total_days > k + 10:
            rho_k = float(daily_returns.autocorr(lag=k))
            if not math.isnan(rho_k):
                autocorr_values.append(rho_k)
                weight = 1.0 - (k / 252.0)
                autocorr_sum += weight * rho_k

    # Lo variance adjustment factor
    lo_factor_variance = 1.0 + 2.0 * autocorr_sum
    lo_factor_variance = max(0.1, lo_factor_variance)
    # Volatility multiplier: if returns are persistent (momentum), real multi-period vol is higher
    lo_vol_multiplier = math.sqrt(lo_factor_variance)
    lo_adjusted_downside = downside_dev * lo_vol_multiplier

    # 6. Cornish-Fisher Tail Penalty (Skewness & Kurtosis)
    ret_values = daily_returns.values
    skew = float(stats.skew(ret_values))
    # Pearson kurtosis (normal distribution = 3.0)
    kurt = float(stats.kurtosis(ret_values, fisher=False))
    excess_kurt = kurt - 3.0

    # Tail penalty: negative skew and positive excess kurtosis increase risk
    tail_penalty = 1.0 - (skew / 6.0) + (excess_kurt / 24.0)
    # Bound penalty so it cannot be negative or absurdly compressed
    tail_penalty = max(0.1, tail_penalty)

    # 7. Ulcer Index & Drawdown Penalty
    cum_max = clean_series.cummax()
    drawdown_series = (clean_series - cum_max) / cum_max
    max_drawdown = float(drawdown_series.min())

    # Ulcer Index: quadratic mean of drawdowns
    ulcer_index = math.sqrt(float(np.mean(drawdown_series.values ** 2)))
    # Ulcer drawdown multiplier
    drawdown_penalty = 1.0 + 2.0 * ulcer_index

    # 8. Ratios
    # Classic Sharpe
    classic_sharpe = annual_excess_return / annual_vol

    # Sortino Ratio
    sortino_ratio = annual_excess_return / downside_dev

    # Combined Single-Stock Quant Sharpe (SSQ-Sharpe)
    total_adjusted_risk = lo_adjusted_downside * tail_penalty * drawdown_penalty
    total_adjusted_risk = max(1e-4, total_adjusted_risk)
    ssq_sharpe = annual_excess_return / total_adjusted_risk

    # Dates
    start_date = clean_series.index[0].strftime("%Y-%m-%d")
    end_date = clean_series.index[-1].strftime("%Y-%m-%d")

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_days": total_days,
        "total_years": round(total_years, 1),
        "start_price": round(start_price, 2),
        "end_price": round(end_price, 2),
        "cagr": cagr,
        "annual_vol": annual_vol,
        "downside_dev": downside_dev,
        "skewness": skew,
        "kurtosis": kurt,
        "excess_kurtosis": excess_kurt,
        "autocorr_lag1": autocorr_values[0] if autocorr_values else 0.0,
        "lo_multiplier": lo_vol_multiplier,
        "tail_penalty": tail_penalty,
        "ulcer_index": ulcer_index,
        "max_drawdown": max_drawdown,
        "drawdown_penalty": drawdown_penalty,
        "classic_sharpe": classic_sharpe,
        "sortino_ratio": sortino_ratio,
        "ssq_sharpe": ssq_sharpe,
    }


def compute_all_sp500_metrics(
    prices_df: pd.DataFrame,
    metadata: Dict[str, Dict[str, str]],
    rf_annual: float = 0.04,
    min_days: int = 252,
) -> pd.DataFrame:
    """
    Computes quant metrics for all tickers in the prices DataFrame.
    Returns a sorted DataFrame containing all metrics and metadata.
    """
    results: List[Dict[str, Any]] = []

    for ticker in prices_df.columns:
        series = prices_df[ticker].dropna()
        metrics = calculate_stock_quant_metrics(series, rf_annual=rf_annual, min_days=min_days)
        if metrics is not None:
            meta = metadata.get(ticker, {})
            record = {
                "ticker": ticker,
                "name": meta.get("name", ticker),
                "sector": meta.get("sector", "Unknown"),
                **metrics,
            }
            results.append(record)

    if not results:
        return pd.DataFrame()

    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values(by="ssq_sharpe", ascending=False).reset_index(drop=True)
    df_results["ssq_rank"] = df_results.index + 1
    # Rank by classic Sharpe for direct comparison
    df_results["classic_rank"] = df_results["classic_sharpe"].rank(ascending=False, method="min").astype(int)
    # Rank delta: positive means SSQ-Sharpe ranks it better than Classic Sharpe
    df_results["rank_delta"] = df_results["classic_rank"] - df_results["ssq_rank"]

    return df_results
