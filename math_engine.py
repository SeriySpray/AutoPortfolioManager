import numpy as np
import pandas as pd
import math
from typing import Dict, Any, Tuple, Optional, List


def compute_hurst_exponent(price_series: np.ndarray, max_lag: int = 20) -> float:
    """
    Estimates Hurst Exponent using variance of differences:
    Var(X(t+tau) - X(t)) ~ tau^(2H)
    H < 0.5: Mean-Reverting / Anti-persistent
    H ~ 0.5: Random Walk (Brownian Motion)
    H > 0.5: Trending / Persistent Momentum
    """
    try:
        ts = price_series[~np.isnan(price_series)]
        n = len(ts)
        if n < max_lag * 2:
            return 0.5

        lags = list(range(2, min(max_lag, n // 3)))
        if len(lags) < 3:
            return 0.5

        tau = [np.std(ts[lag:] - ts[:-lag]) for lag in lags]
        valid = [(l, t) for l, t in zip(lags, tau) if t > 1e-9]
        if len(valid) < 3:
            return 0.5

        log_lags = np.log([v[0] for v in valid])
        log_tau = np.log([v[1] for v in valid])

        poly = np.polyfit(log_lags, log_tau, 1)
        h = float(poly[0])
        return float(np.clip(h, 0.0, 1.0))
    except Exception:
        return 0.5


def compute_ou_half_life(series: np.ndarray) -> Tuple[float, float]:
    """
    Fits Ornstein-Uhlenbeck AR(1) discrete process:
    ΔX_t = α + β * X_{t-1} + ε_t
    Returns: (theta, half_life_bars) where half_life = ln(2)/theta
    """
    try:
        x = series[~np.isnan(series)]
        if len(x) < 5:
            return 0.0, 999.0

        x_lag = x[:-1]
        dx = x[1:] - x_lag

        poly = np.polyfit(x_lag, dx, 1)
        beta = float(poly[0])

        if beta >= 0:
            return 0.0, 999.0

        theta = -beta
        half_life = float(np.log(2.0) / theta)
        return round(theta, 4), round(max(0.1, min(999.0, half_life)), 1)
    except Exception:
        return 0.0, 999.0


def compute_ar1_weight(log_returns: np.ndarray) -> Tuple[float, float]:
    """
    Fits univariate AR(1) autoregression on log returns:
    r_t = w * r_{t-1} + b
    w < 0: Mean Reversion tendency
    w > 0: Momentum / Trend persistence tendency
    """
    try:
        r = log_returns[~np.isnan(log_returns)]
        if len(r) < 5:
            return 0.0, 0.0

        r_lag = r[:-1]
        r_curr = r[1:]

        poly = np.polyfit(r_lag, r_curr, 1)
        w = float(poly[0])
        b = float(poly[1])
        return round(w, 4), round(b, 6)
    except Exception:
        return 0.0, 0.0


def compute_atr(df: pd.DataFrame, period: int = 14) -> Tuple[float, float]:
    """
    Computes Average True Range (ATR) in absolute dollars and as a % of price.
    TR = max(High - Low, abs(High - Close_prev), abs(Low - Close_prev))
    """
    try:
        if len(df) < 2:
            return 0.0, 0.0
        high = df["High"].astype(float).values
        low = df["Low"].astype(float).values
        close = df["Close"].astype(float).values
        
        tr = np.zeros(len(df))
        tr[0] = high[0] - low[0]
        for i in range(1, len(df)):
            tr1 = high[i] - low[i]
            tr2 = abs(high[i] - close[i - 1])
            tr3 = abs(low[i] - close[i - 1])
            tr[i] = max(tr1, tr2, tr3)
        
        atr_window = tr[-min(period, len(tr)):]
        atr_val = float(np.mean(atr_window))
        last_close = float(close[-1])
        atr_pct = float((atr_val / last_close) * 100.0) if last_close > 0 else 0.0
        return round(atr_val, 3), round(atr_pct, 2)
    except Exception:
        return 0.0, 0.0


def compute_choppiness_index(df: pd.DataFrame, period: int = 14) -> float:
    """
    Choppiness Index (CHOP):
    CHOP = 100 * LOG10( SUM(ATR(1), n) / (MaxHigh(n) - MinLow(n)) ) / LOG10(n)
    CHOP > 61.8: Market is consolidating / Choppy / Sideways
    CHOP < 38.2: Market is strongly trending
    """
    try:
        n = min(period, len(df))
        if n < 3:
            return 50.0
        sub_df = df.iloc[-n:]
        high = sub_df["High"].astype(float).values
        low = sub_df["Low"].astype(float).values
        close = sub_df["Close"].astype(float).values

        tr_sum = 0.0
        for i in range(len(sub_df)):
            if i == 0:
                tr_sum += high[0] - low[0]
            else:
                tr_sum += max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))

        max_h = np.max(high)
        min_l = np.min(low)
        range_hl = max_h - min_l

        if range_hl <= 1e-6 or tr_sum <= 1e-6:
            return 50.0

        chop = 100.0 * (math.log10(tr_sum / range_hl) / math.log10(n))
        return float(np.clip(chop, 0.0, 100.0))
    except Exception:
        return 50.0


def compute_window_math_metrics(train_df: pd.DataFrame) -> Dict[str, float]:
    """
    Computes pure quantitative mathematical & statistical metrics strictly on an isolated training slice.
    Zero future data leakage.
    """
    if train_df.empty or len(train_df) < 3:
        return {}

    close = train_df["Close"].astype(float).values
    n = len(close)
    first_p = float(close[0])
    last_p = float(close[-1])
    min_p = float(np.min(close))
    max_p = float(np.max(close))

    # 1. Basic price statistics
    mean_p = float(np.mean(close))
    std_p = float(np.std(close, ddof=1)) if n > 1 else 1e-6
    std_p_safe = std_p if std_p > 1e-9 else 1e-6
    var_p = float(np.var(close, ddof=1)) if n > 1 else 1e-6
    zscore = float((last_p - mean_p) / std_p_safe)

    # 2. Returns & Log Returns
    return_pct = float(((last_p - first_p) / first_p) * 100.0) if first_p > 0 else 0.0
    log_return = float(np.log(last_p / first_p)) if (first_p > 0 and last_p > 0) else 0.0

    # Daily log returns series on window
    safe_close = np.where(close <= 0, 1e-6, close)
    daily_log_rets = np.diff(np.log(safe_close)) if n > 1 else np.array([0.0])
    
    # 3. Volatility & Downside Deviation
    volatility_ann = float(np.std(daily_log_rets, ddof=1) * np.sqrt(252) * 100.0) if len(daily_log_rets) > 1 else 0.0
    neg_rets = daily_log_rets[daily_log_rets < 0]
    downside_std_ann = float(np.std(neg_rets, ddof=1) * np.sqrt(252) * 100.0) if len(neg_rets) > 1 else 1e-6

    # Window Sharpe & Sortino
    mean_daily_ret = float(np.mean(daily_log_rets)) if len(daily_log_rets) > 0 else 0.0
    daily_vol = float(np.std(daily_log_rets, ddof=1)) if len(daily_log_rets) > 1 else 1e-6
    window_sharpe = float((mean_daily_ret / daily_vol) * np.sqrt(252)) if daily_vol > 1e-9 else 0.0
    window_sortino = float((mean_daily_ret / (np.std(neg_rets, ddof=1) if len(neg_rets) > 1 else 1e-6)) * np.sqrt(252))

    # 4. Econometric AR(1) dynamics
    ar1_w, ar1_b = compute_ar1_weight(daily_log_rets)

    # 5. Ornstein-Uhlenbeck Speed & Half-Life
    ou_theta, half_life = compute_ou_half_life(close)

    # 6. Hurst Exponent
    hurst = compute_hurst_exponent(close)

    # 7. Linear Regression (Slope % per bar, R^2)
    x = np.arange(n)
    norm_y = close / first_p if first_p > 0 else close
    poly, residuals, _, _, _ = np.polyfit(x, norm_y, 1, full=True)
    slope_pct = float(poly[0]) * 100.0

    y_pred = poly[0] * x + poly[1]
    ss_tot = np.sum((norm_y - np.mean(norm_y)) ** 2)
    ss_res = np.sum((norm_y - y_pred) ** 2)
    r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-9 else 0.0
    r2 = float(np.clip(r2, 0.0, 1.0))

    # Fast 3-bar slope & Delta Slope for V-Reversal detection
    if n >= 4:
        fast_x = np.arange(3)
        fast_y = close[-3:] / close[-3]
        fast_p = np.polyfit(fast_x, fast_y, 1)
        fast_slope_pct = float(fast_p[0]) * 100.0
        delta_slope = float(fast_slope_pct - slope_pct)
    else:
        fast_slope_pct = slope_pct
        delta_slope = 0.0

    # 8. Polynomial 2nd degree (Curvature = 2*a, Final Slope)
    p2 = np.polyfit(x, norm_y, 2)
    curvature = 2.0 * float(p2[0])
    final_slope = 2.0 * float(p2[0]) * (n - 1) + float(p2[1])

    # 9. ATR & Choppiness Index
    atr_val, atr_pct = compute_atr(train_df, period=14)
    chop_index = compute_choppiness_index(train_df, period=14)

    # 10. Drawdown / Distance from High & Low
    dist_high_pct = float(((last_p - max_p) / max_p) * 100.0) if max_p > 0 else 0.0
    dist_low_pct = float(((last_p - min_p) / min_p) * 100.0) if min_p > 0 else 0.0

    # 11. RSI
    if n >= 14:
        diffs = np.diff(close)
        gains = np.where(diffs > 0, diffs, 0.0)
        losses = np.where(diffs < 0, -diffs, 0.0)
        avg_g = np.mean(gains[-14:])
        avg_l = np.mean(losses[-14:])
        rs = avg_g / (avg_l if avg_l > 1e-9 else 1e-6)
        rsi = float(100.0 - (100.0 / (1.0 + rs)))
    else:
        rsi = 50.0

    return {
        "bars": n,
        "first_price": round(first_p, 4),
        "last_price": round(last_p, 4),
        "min_price": round(min_p, 4),
        "max_price": round(max_p, 4),
        "mean": round(mean_p, 4),
        "std": round(std_p, 4),
        "variance": round(var_p, 4),
        "zscore": round(zscore, 3),
        "return_pct": round(return_pct, 2),
        "log_return": round(log_return, 4),
        "volatility_ann": round(volatility_ann, 2),
        "downside_std_ann": round(downside_std_ann, 2),
        "window_sharpe": round(window_sharpe, 2),
        "window_sortino": round(window_sortino, 2),
        "ar1_w": round(ar1_w, 4),
        "ar1_b": round(ar1_b, 6),
        "ou_theta": round(ou_theta, 4),
        "half_life": round(half_life, 1),
        "hurst": round(hurst, 3),
        "slope": round(slope_pct, 3),
        "fast_slope": round(fast_slope_pct, 3),
        "delta_slope": round(delta_slope, 3),
        "r2": round(r2, 3),
        "curvature": round(curvature, 6),
        "final_slope": round(final_slope, 4),
        "atr_val": atr_val,
        "atr_pct": atr_pct,
        "chop_index": round(chop_index, 1),
        "dist_to_high_pct": round(dist_high_pct, 2),
        "dist_to_low_pct": round(dist_low_pct, 2),
        "rsi": round(rsi, 2)
    }


def safe_eval_condition(expr: str, context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Safely evaluates a user mathematical condition string."""
    if not expr or not expr.strip():
        return False, None

    clean_expr = expr.strip()
    safe_dict = {
        "abs": abs,
        "min": min,
        "max": max,
        "sqrt": math.sqrt,
        "log": math.log,
        "exp": math.exp,
        "math": math,
        "np": np
    }
    safe_dict.update(context)

    try:
        res = eval(clean_expr, {"__builtins__": {}}, safe_dict)
        return bool(res), None
    except Exception as e:
        return False, f"Помилка формули '{clean_expr}': {str(e)}"


class MultiFactorModel:
    """
    Multi-Parameter Quantitative Factor Engine with V-Reversal Circuit Breaker & Chop Filter.
    """

    @classmethod
    def compute_composite_alpha(
        cls,
        metrics: Dict[str, Any],
        w_mean_revert: float = 0.35,
        w_momentum: float = 0.35,
        w_ar1: float = 0.20,
        w_curv: float = 0.10,
        use_regime_switch: bool = True,
        use_chop_filter: bool = True,
        use_v_reversal_breaker: bool = True
    ) -> Dict[str, Any]:
        if not metrics:
            return {"composite_score": 0.0, "factor_scores": {}}

        # Factor 1: Mean Reversion Score
        z = float(metrics.get("zscore", 0.0))
        f_mr = -float(np.clip(z / 2.5, -1.0, 1.0))

        # Factor 2: Momentum Score
        slope = float(metrics.get("slope", 0.0))
        r2 = float(metrics.get("r2", 0.0))
        f_mom = float(np.clip(slope / 0.3, -1.0, 1.0)) * (0.3 + 0.7 * r2)

        # Factor 3: AR(1) Weight Signal
        w_ar = float(metrics.get("ar1_w", 0.0))
        f_ar1 = float(np.clip(w_ar / 0.5, -1.0, 1.0))

        # Factor 4: Acceleration / Curvature
        curv = float(metrics.get("curvature", 0.0))
        f_curv = float(np.clip(curv * 500.0, -1.0, 1.0))

        # Regime-Adaptive Weight Adjustment (Hurst Exponent)
        hurst = float(metrics.get("hurst", 0.5))
        eff_w_mr = w_mean_revert
        eff_w_mom = w_momentum

        if use_regime_switch:
            if hurst > 0.52:
                eff_w_mom *= (1.0 + (hurst - 0.5) * 2.0)
                eff_w_mr *= (1.0 - (hurst - 0.5) * 1.5)
            elif hurst < 0.48:
                eff_w_mr *= (1.0 + (0.5 - hurst) * 2.0)
                eff_w_mom *= (1.0 - (0.5 - hurst) * 1.5)

        # Normalize weights
        total_w = max(1e-6, eff_w_mr + eff_w_mom + w_ar1 + w_curv)
        eff_w_mr /= total_w
        eff_w_mom /= total_w
        w_ar1_norm = w_ar1 / total_w
        w_curv_norm = w_curv / total_w

        composite_score = (
            eff_w_mr * f_mr +
            eff_w_mom * f_mom +
            w_ar1_norm * f_ar1 +
            w_curv_norm * f_curv
        )

        # Chop Filter: Dampen score if market is in high chop/consolidation (CHOP > 60)
        chop = float(metrics.get("chop_index", 50.0))
        if use_chop_filter and chop > 60.0:
            dampener = float(np.clip(1.0 - (chop - 60.0) / 40.0, 0.2, 1.0))
            composite_score *= dampener

        # V-Reversal Circuit Breaker: If fast slope indicates sudden upward surge, veto short signals
        delta_slope = float(metrics.get("delta_slope", 0.0))
        if use_v_reversal_breaker and composite_score < 0 and delta_slope > 0.15:
            composite_score = 0.0  # neutralize short on violent V-bottom rebound

        composite_score = float(np.clip(composite_score, -1.0, 1.0))

        return {
            "composite_score": round(composite_score, 4),
            "factor_scores": {
                "mean_reversion": round(f_mr, 3),
                "momentum": round(f_mom, 3),
                "ar1": round(f_ar1, 3),
                "curvature": round(f_curv, 3),
                "hurst_regime": round(hurst, 3),
                "chop_index": round(chop, 1)
            },
            "weights_used": {
                "w_mean_revert": round(eff_w_mr, 3),
                "w_momentum": round(eff_w_mom, 3),
                "w_ar1": round(w_ar1_norm, 3),
                "w_curv": round(w_curv_norm, 3)
            }
        }


def compute_position_size(
    direction: int,
    signal_strength: float,
    volatility_ann: float = 20.0,
    sizing_mode: str = "tanh",
    max_size: float = 1.0
) -> float:
    if direction == 0 or abs(signal_strength) < 1e-5:
        return 0.0

    sig = abs(signal_strength)

    if sizing_mode == "constant":
        return float(direction * max_size)

    elif sizing_mode == "hardtanh":
        scaled = np.clip(sig * 1.5, 0.1, 1.0)
        return float(direction * max_size * scaled)

    elif sizing_mode == "tanh":
        scaled = float(np.tanh(sig * 2.0))
        return float(direction * max_size * scaled)

    elif sizing_mode == "kelly":
        vol = max(10.0, volatility_ann)
        scaled = float(np.clip((sig * 30.0) / vol, 0.15, 1.0))
        return float(direction * max_size * scaled)

    return float(direction * max_size)


class MathEngine:
    """
    Quantitative Analysis, Multi-Factor Synthesis, and Blind Forecasting Engine.
    """

    AVAILABLE_VARIABLES = [
        {"name": "zscore", "description": "Z-Score відхилення від середнього на вікні (у стандартних відхиленнях σ)"},
        {"name": "ar1_w", "description": "Вага авторегресії AR(1) на лог-дохідностях: w < 0 (Mean Reversion), w > 0 (Momentum)"},
        {"name": "hurst", "description": "Показник Херста H: H < 0.5 (Mean Reverting), H = 0.5 (Random Walk), H > 0.5 (Trending)"},
        {"name": "half_life", "description": "Період напіврозпаду відхилення Ornstein-Uhlenbeck у свічках (t_1/2 = ln(2)/theta)"},
        {"name": "ou_theta", "description": "Швидкість повернення до середнього Ornstein-Uhlenbeck (theta)"},
        {"name": "slope", "description": "Кут нахилу лінійного тренду (% зміни ціни за 1 свічку)"},
        {"name": "fast_slope", "description": "Швидкий нахил останніх 3 свічок (% за свічку)"},
        {"name": "delta_slope", "description": "Прискорення зміни нахилу (Fast Slope - Baseline Slope)"},
        {"name": "r2", "description": "Коефіцієнт детермінації лінійного тренду R² (від 0.0 до 1.0)"},
        {"name": "atr_pct", "description": "Average True Range у % від поточної ціни (волатильність діапазону)"},
        {"name": "chop_index", "description": "Choppiness Index (CHOP): > 61.8 (Флет/Пила), < 38.2 (Сильний тренд)"},
        {"name": "return_pct", "description": "Загальна зміна ціни на вікні у відсотках (%)"},
        {"name": "log_return", "description": "Адитивна логарифмічна дохідність на вікні ln(P_last / P_first)"},
        {"name": "volatility_ann", "description": "Річна волатильність лог-дохідностей на вікні (%)"},
        {"name": "downside_std_ann", "description": "Річна волатильність спадних дохідностей (Downside Risk, %)"},
        {"name": "window_sharpe", "description": "Локальний коефіцієнт Шарпа на тренувальному вікні"},
        {"name": "window_sortino", "description": "Локальний коефіцієнт Сортіно на тренувальному вікні"},
        {"name": "curvature", "description": "Поліноміальне прискорення (2-га похідна цінової кривої)"},
        {"name": "rsi", "description": "Індекс відносної сили RSI на вікні (0-100)"},
        {"name": "mean", "description": "Середня ціна на вікні"},
        {"name": "std", "description": "Стандартне відхилення ціни на вікні"},
        {"name": "last_price", "description": "Остання ціна на вікні"}
    ]

    @classmethod
    def evaluate_train_window(
        cls,
        train_df: pd.DataFrame,
        condition_up: str = "",
        condition_down: str = "",
        sizing_mode: str = "constant"
    ) -> Dict[str, Any]:
        metrics = compute_window_math_metrics(train_df)
        if not metrics:
            return {
                "direction": 0, "position_size": 0.0, "confidence": 0.0,
                "metrics": {}, "reason": "Недостатньо свічок на вікні", "error": None
            }

        is_up, err_up = safe_eval_condition(condition_up, metrics) if condition_up else (False, None)
        is_down, err_down = safe_eval_condition(condition_down, metrics) if condition_down else (False, None)

        if err_up:
            return {"direction": 0, "position_size": 0.0, "confidence": 0.0, "metrics": metrics, "reason": err_up, "error": err_up}
        if err_down:
            return {"direction": 0, "position_size": 0.0, "confidence": 0.0, "metrics": metrics, "reason": err_down, "error": err_down}

        direction = 0
        reason = "Умови не виконані (Нейтрально)"

        if is_up and not is_down:
            direction = 1
            reason = f"Умова UP: {condition_up}"
        elif is_down and not is_up:
            direction = -1
            reason = f"Умова DOWN: {condition_down}"
        elif is_up and is_down:
            direction = 0
            reason = "Конфлікт: одночасно виконані умови UP та DOWN"

        sig_strength = abs(metrics.get("zscore", 1.0)) / 2.0
        pos_size = compute_position_size(
            direction=direction,
            signal_strength=sig_strength,
            volatility_ann=metrics.get("volatility_ann", 20.0),
            sizing_mode=sizing_mode
        )

        return {
            "direction": direction,
            "position_size": round(pos_size, 3),
            "confidence": round(abs(pos_size), 2),
            "metrics": metrics,
            "reason": reason,
            "error": None
        }

    @classmethod
    def evaluate_multi_factor_window(
        cls,
        train_df: pd.DataFrame,
        w_mean_revert: float = 0.35,
        w_momentum: float = 0.35,
        w_ar1: float = 0.20,
        w_curv: float = 0.10,
        threshold_up: float = 0.15,
        threshold_down: float = -0.15,
        sizing_mode: str = "tanh",
        use_chop_filter: bool = True,
        use_v_reversal_breaker: bool = True
    ) -> Dict[str, Any]:
        metrics = compute_window_math_metrics(train_df)
        if not metrics:
            return {
                "direction": 0, "position_size": 0.0, "confidence": 0.0, "composite_score": 0.0,
                "metrics": {}, "reason": "Недостатньо свічок", "error": None
            }

        alpha_res = MultiFactorModel.compute_composite_alpha(
            metrics=metrics,
            w_mean_revert=w_mean_revert,
            w_momentum=w_momentum,
            w_ar1=w_ar1,
            w_curv=w_curv,
            use_regime_switch=True,
            use_chop_filter=use_chop_filter,
            use_v_reversal_breaker=use_v_reversal_breaker
        )

        comp_score = alpha_res["composite_score"]
        direction = 0
        reason = f"Composite Score = {comp_score:.3f} (у нейтральній зоні [{threshold_down:.2f}, {threshold_up:.2f}])"

        if comp_score >= threshold_up:
            direction = 1
            reason = f"Бичачий мультифакторний сигнал: Score {comp_score:.3f} >= {threshold_up:.2f}"
        elif comp_score <= threshold_down:
            direction = -1
            reason = f"Ведмежий мультифакторний сигнал: Score {comp_score:.3f} <= {threshold_down:.2f}"

        pos_size = compute_position_size(
            direction=direction,
            signal_strength=abs(comp_score),
            volatility_ann=metrics.get("volatility_ann", 20.0),
            sizing_mode=sizing_mode
        )

        metrics["composite_score"] = comp_score
        metrics["factor_scores"] = alpha_res["factor_scores"]

        return {
            "direction": direction,
            "position_size": round(pos_size, 3),
            "confidence": round(abs(comp_score), 3),
            "composite_score": comp_score,
            "metrics": metrics,
            "factor_scores": alpha_res["factor_scores"],
            "reason": reason,
            "error": None
        }
