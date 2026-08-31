import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from math_engine import MathEngine, MultiFactorModel


class WalkForwardBacktester:
    """
    Pure Walk-Forward quantitative validation and risk-adjusted backtesting engine.
    Enhanced with:
      1. Dynamic ATR Volatility Stop-Loss & Take-Profit Barriers (Triple Barrier Simulation)
      2. V-Reversal Acceleration Circuit Breaker
      3. Chop Filtering & Kelly Sizing
    """

    def __init__(self, data: pd.DataFrame):
        self.df = data.copy()
        if not self.df.empty:
            self.df["Date"] = pd.to_datetime(self.df["Date"])
            self.df = self.df.sort_values("Date").drop_duplicates(subset=["Date"]).reset_index(drop=True)
            for col in ["Open", "High", "Low", "Close"]:
                if col in self.df.columns:
                    self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

    def run_walk_forward(
        self,
        train_bars: int = 60,
        predict_bars: int = 15,
        step_bars: int = 15,
        condition_up: str = "",
        condition_down: str = "",
        sizing_mode: str = "constant",
        fee_pct: float = 0.05,
        atr_stop_loss_mult: float = 0.0,
        atr_take_profit_mult: float = 0.0
    ) -> Dict[str, Any]:
        """Custom formula / condition walk-forward backtest."""
        return self._execute_walk_forward_loop(
            train_bars=train_bars,
            predict_bars=predict_bars,
            step_bars=step_bars,
            is_multi_factor=False,
            condition_up=condition_up,
            condition_down=condition_down,
            sizing_mode=sizing_mode,
            fee_pct=fee_pct,
            atr_stop_loss_mult=atr_stop_loss_mult,
            atr_take_profit_mult=atr_take_profit_mult
        )

    def run_multi_factor_walk_forward(
        self,
        train_bars: int = 60,
        predict_bars: int = 15,
        step_bars: int = 15,
        w_mean_revert: float = 0.35,
        w_momentum: float = 0.35,
        w_ar1: float = 0.20,
        w_curv: float = 0.10,
        threshold_up: float = 0.15,
        threshold_down: float = -0.15,
        sizing_mode: str = "tanh",
        fee_pct: float = 0.05,
        atr_stop_loss_mult: float = 2.0,
        atr_take_profit_mult: float = 0.0,
        use_chop_filter: bool = True,
        use_v_reversal_breaker: bool = True
    ) -> Dict[str, Any]:
        """Multi-Parameter Quantitative Factor Walk-Forward backtest with ATR barriers."""
        return self._execute_walk_forward_loop(
            train_bars=train_bars,
            predict_bars=predict_bars,
            step_bars=step_bars,
            is_multi_factor=True,
            w_mean_revert=w_mean_revert,
            w_momentum=w_momentum,
            w_ar1=w_ar1,
            w_curv=w_curv,
            threshold_up=threshold_up,
            threshold_down=threshold_down,
            sizing_mode=sizing_mode,
            fee_pct=fee_pct,
            atr_stop_loss_mult=atr_stop_loss_mult,
            atr_take_profit_mult=atr_take_profit_mult,
            use_chop_filter=use_chop_filter,
            use_v_reversal_breaker=use_v_reversal_breaker
        )

    def _execute_walk_forward_loop(
        self,
        train_bars: int,
        predict_bars: int,
        step_bars: int,
        is_multi_factor: bool = False,
        condition_up: str = "",
        condition_down: str = "",
        w_mean_revert: float = 0.35,
        w_momentum: float = 0.35,
        w_ar1: float = 0.20,
        w_curv: float = 0.10,
        threshold_up: float = 0.15,
        threshold_down: float = -0.15,
        sizing_mode: str = "tanh",
        fee_pct: float = 0.05,
        atr_stop_loss_mult: float = 0.0,
        atr_take_profit_mult: float = 0.0,
        use_chop_filter: bool = True,
        use_v_reversal_breaker: bool = True
    ) -> Dict[str, Any]:
        df = self.df
        n = len(df)
        min_required = train_bars + predict_bars

        if n < min_required:
            return {
                "success": False,
                "error": f"Недостатньо даних: потрібно мінімум {min_required} свічок, доступно {n}."
            }

        predictions: List[Dict[str, Any]] = []
        equity_curve = []
        
        initial_price = float(df["Close"].iloc[train_bars - 1])
        current_equity = 100.0

        i = 0
        while i + train_bars + predict_bars <= n:
            train_slice = df.iloc[i : i + train_bars]
            test_slice = df.iloc[i + train_bars : i + train_bars + predict_bars]

            train_start_date = train_slice["Date"].iloc[0].strftime("%Y-%m-%d")
            train_end_date = train_slice["Date"].iloc[-1].strftime("%Y-%m-%d")
            test_start_date = test_slice["Date"].iloc[0].strftime("%Y-%m-%d")
            test_end_date = test_slice["Date"].iloc[-1].strftime("%Y-%m-%d")

            # 1. In-Sample Model Evaluation strictly on train_slice
            if is_multi_factor:
                eval_res = MathEngine.evaluate_multi_factor_window(
                    train_df=train_slice,
                    w_mean_revert=w_mean_revert,
                    w_momentum=w_momentum,
                    w_ar1=w_ar1,
                    w_curv=w_curv,
                    threshold_up=threshold_up,
                    threshold_down=threshold_down,
                    sizing_mode=sizing_mode,
                    use_chop_filter=use_chop_filter,
                    use_v_reversal_breaker=use_v_reversal_breaker
                )
            else:
                eval_res = MathEngine.evaluate_train_window(
                    train_df=train_slice,
                    condition_up=condition_up,
                    condition_down=condition_down,
                    sizing_mode=sizing_mode
                )

            pred_direction = eval_res.get("direction", 0)
            pos_size = eval_res.get("position_size", 0.0)
            confidence = eval_res.get("confidence", 0.0)
            reason = eval_res.get("reason", "")
            metrics = eval_res.get("metrics", {})

            price_start = float(train_slice["Close"].iloc[-1])
            atr_pct = float(metrics.get("atr_pct", 2.5))
            
            # 2. Intra-Window Path Simulation with ATR Barriers
            exit_price = float(test_slice["Close"].iloc[-1])
            exit_reason = "Часовий горизонт завершено (Time Horizon)"
            sl_hit = False
            tp_hit = False

            if pred_direction != 0:
                sl_barrier_pct = (atr_stop_loss_mult * atr_pct) if atr_stop_loss_mult > 0 else 999.0
                tp_barrier_pct = (atr_take_profit_mult * atr_pct) if atr_take_profit_mult > 0 else 999.0

                test_closes = test_slice["Close"].values
                test_lows = test_slice["Low"].values if "Low" in test_slice.columns else test_closes
                test_highs = test_slice["High"].values if "High" in test_slice.columns else test_closes

                for bar_idx in range(len(test_slice)):
                    curr_close = float(test_closes[bar_idx])
                    curr_low = float(test_lows[bar_idx])
                    curr_high = float(test_highs[bar_idx])

                    if pred_direction == 1:
                        # Long position: SL if price drops below barrier
                        drawdown_pct = ((price_start - curr_low) / price_start) * 100.0
                        gain_pct = ((curr_high - price_start) / price_start) * 100.0

                        if sl_barrier_pct < 900 and drawdown_pct >= sl_barrier_pct:
                            exit_price = max(0.01, price_start * (1.0 - sl_barrier_pct / 100.0))
                            exit_reason = f"ATR Stop-Loss ({sl_barrier_pct:.1f}%) на свічці +{bar_idx+1}"
                            sl_hit = True
                            break
                        elif tp_barrier_pct < 900 and gain_pct >= tp_barrier_pct:
                            exit_price = price_start * (1.0 + tp_barrier_pct / 100.0)
                            exit_reason = f"ATR Take-Profit (+{tp_barrier_pct:.1f}%) на свічці +{bar_idx+1}"
                            tp_hit = True
                            break

                    elif pred_direction == -1:
                        # Short position: SL if price rises above barrier
                        loss_pct = ((curr_high - price_start) / price_start) * 100.0
                        gain_pct = ((price_start - curr_low) / price_start) * 100.0

                        if sl_barrier_pct < 900 and loss_pct >= sl_barrier_pct:
                            exit_price = price_start * (1.0 + sl_barrier_pct / 100.0)
                            exit_reason = f"ATR Stop-Loss (-{sl_barrier_pct:.1f}%) на свічці +{bar_idx+1}"
                            sl_hit = True
                            break
                        elif tp_barrier_pct < 900 and gain_pct >= tp_barrier_pct:
                            exit_price = max(0.01, price_start * (1.0 - tp_barrier_pct / 100.0))
                            exit_reason = f"ATR Take-Profit (+{tp_barrier_pct:.1f}%) на свічці +{bar_idx+1}"
                            tp_hit = True
                            break

            actual_return_pct = float(((exit_price - price_start) / price_start) * 100.0) if price_start > 0 else 0.0
            actual_log_ret = float(np.log(exit_price / price_start)) if (price_start > 0 and exit_price > 0) else 0.0

            if actual_return_pct > 0.0:
                actual_direction = 1
            elif actual_return_pct < 0.0:
                actual_direction = -1
            else:
                actual_direction = 0

            # 3. Determine Correctness & Sized Strategy Return
            is_correct = None
            strategy_return_pct = 0.0

            if pred_direction != 0:
                strategy_return_pct = (pos_size * actual_return_pct) - (abs(pos_size) * fee_pct)
                if pred_direction == 1:
                    is_correct = (actual_return_pct > 0.0)
                elif pred_direction == -1:
                    is_correct = (actual_return_pct < 0.0)
            else:
                strategy_return_pct = 0.0
                is_correct = None

            # Portfolio Compounding with Bankruptcy Protection
            if current_equity > 0.0:
                mult = 1.0 + (strategy_return_pct / 100.0)
                current_equity = max(0.0, current_equity * mult)
            else:
                current_equity = 0.0

            bh_price_end = float(test_slice["Close"].iloc[-1])
            bh_equity = max(0.0, 100.0 * (bh_price_end / initial_price)) if initial_price > 0 else 100.0

            equity_curve.append({
                "date": test_end_date,
                "strategy_equity": round(current_equity, 2),
                "buy_hold_equity": round(bh_equity, 2)
            })

            predictions.append({
                "window_index": len(predictions) + 1,
                "train_start": train_start_date,
                "train_end": train_end_date,
                "test_start": test_start_date,
                "test_end": test_end_date,
                "train_bars": len(train_slice),
                "test_bars": len(test_slice),
                "predicted_direction": pred_direction,
                "position_size": pos_size,
                "confidence": confidence,
                "reason": reason,
                "exit_reason": exit_reason,
                "price_start": round(price_start, 2),
                "price_end": round(exit_price, 2),
                "actual_return_pct": round(actual_return_pct, 2),
                "actual_log_ret": round(actual_log_ret, 4),
                "actual_direction": actual_direction,
                "is_correct": is_correct,
                "strategy_return_pct": round(strategy_return_pct, 2),
                "equity_after": round(current_equity, 2),
                "metrics": metrics
            })

            i += step_bars

        # 4. Aggregations & Quantitative Statistics
        total_windows = len(predictions)
        active_preds = [p for p in predictions if p["predicted_direction"] != 0]
        active_count = len(active_preds)
        neutral_count = total_windows - active_count

        correct_count = sum(1 for p in active_preds if p["is_correct"] is True)
        incorrect_count = sum(1 for p in active_preds if p["is_correct"] is False)
        accuracy_pct = (correct_count / active_count * 100.0) if active_count > 0 else 0.0

        active_returns = [p["strategy_return_pct"] for p in active_preds]
        gains = [r for r in active_returns if r > 0]
        losses = [abs(r) for r in active_returns if r < 0]

        total_gain = sum(gains)
        total_loss = sum(losses)
        avg_win = float(np.mean(gains)) if len(gains) > 0 else 0.0
        avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0

        win_rate = (len(gains) / active_count * 100.0) if active_count > 0 else 0.0
        loss_rate = (len(losses) / active_count * 100.0) if active_count > 0 else 0.0

        p_win = len(gains) / active_count if active_count > 0 else 0.0
        p_loss = len(losses) / active_count if active_count > 0 else 0.0
        expected_value = (p_win * avg_win) - (p_loss * avg_loss)

        profit_factor = round(total_gain / total_loss, 2) if total_loss > 0 else (99.0 if total_gain > 0 else 1.0)
        win_loss_payoff = round(avg_win / avg_loss, 2) if avg_loss > 0 else 99.0
        avg_trade_ret = float(np.mean(active_returns)) if active_count > 0 else 0.0

        # Max Drawdown
        equities = [p["equity_after"] for p in predictions]
        peak = 100.0
        max_dd = 0.0
        for eq in equities:
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = ((peak - eq) / peak) * 100.0
                if dd > max_dd:
                    max_dd = dd

        # Annualized Sharpe & Sortino Ratio
        mean_ret = np.mean(active_returns) if active_count > 0 else 0.0
        std_ret = np.std(active_returns, ddof=1) if active_count > 1 else 1e-6
        periods_per_year = max(1.0, 252.0 / max(1, step_bars))
        sharpe = (mean_ret / (std_ret if std_ret > 1e-9 else 1e-6)) * np.sqrt(periods_per_year) if active_count > 1 else 0.0

        downside_returns = [r for r in active_returns if r < 0]
        downside_std = np.std(downside_returns, ddof=1) if len(downside_returns) > 1 else 1e-6
        sortino = (mean_ret / (downside_std if downside_std > 1e-9 else 1e-6)) * np.sqrt(periods_per_year) if len(downside_returns) > 1 else 0.0

        total_strategy_return = round(current_equity - 100.0, 2)
        last_price_overall = float(df["Close"].iloc[-1])
        total_bh_return = round(((last_price_overall - initial_price) / initial_price) * 100.0, 2) if initial_price > 0 else 0.0

        total_years = max(0.1, (len(df) / 252.0))
        cagr = (max(0.001, current_equity / 100.0) ** (1.0 / total_years) - 1.0) * 100.0
        calmar = round(cagr / max(1.0, max_dd), 2)

        return {
            "success": True,
            "is_multi_factor": is_multi_factor,
            "total_windows": total_windows,
            "active_trades": active_count,
            "correct_trades": correct_count,
            "incorrect_trades": incorrect_count,
            "neutral_windows": neutral_count,
            "accuracy_pct": round(accuracy_pct, 2),
            "win_rate_pct": round(win_rate, 2),
            "loss_rate_pct": round(loss_rate, 2),
            "expected_value_pct": round(expected_value, 3),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "win_loss_payoff": win_loss_payoff,
            "avg_trade_return_pct": round(avg_trade_ret, 2),
            "total_return_pct": total_strategy_return,
            "buy_and_hold_return_pct": total_bh_return,
            "max_drawdown_pct": round(max_dd, 2),
            "profit_factor": profit_factor,
            "sharpe_ratio": round(float(sharpe), 2),
            "sortino_ratio": round(float(sortino), 2),
            "calmar_ratio": calmar,
            "equity_curve": equity_curve,
            "predictions": predictions
        }

    def generate_latest_blind_forecast(
        self,
        train_bars: int = 60,
        predict_bars: int = 15,
        w_mean_revert: float = 0.35,
        w_momentum: float = 0.35,
        w_ar1: float = 0.20,
        w_curv: float = 0.10,
        threshold_up: float = 0.15,
        threshold_down: float = -0.15,
        sizing_mode: str = "tanh",
        atr_stop_loss_mult: float = 2.0
    ) -> Dict[str, Any]:
        df = self.df
        n = len(df)
        if n < train_bars:
            return {"success": False, "error": "Недостатньо історичних даних для аналізу поточного вікна"}

        latest_train_slice = df.iloc[-train_bars:]
        last_date = latest_train_slice["Date"].iloc[-1].strftime("%Y-%m-%d")
        last_price = float(latest_train_slice["Close"].iloc[-1])

        eval_res = MathEngine.evaluate_multi_factor_window(
            train_df=latest_train_slice,
            w_mean_revert=w_mean_revert,
            w_momentum=w_momentum,
            w_ar1=w_ar1,
            w_curv=w_curv,
            threshold_up=threshold_up,
            threshold_down=threshold_down,
            sizing_mode=sizing_mode,
            use_chop_filter=True,
            use_v_reversal_breaker=True
        )

        direction = eval_res["direction"]
        comp_score = eval_res["composite_score"]
        pos_size = eval_res["position_size"]
        metrics = eval_res["metrics"]
        factor_scores = eval_res["factor_scores"]

        atr_val = float(metrics.get("atr_val", 2.0))
        atr_pct = float(metrics.get("atr_pct", 2.5))

        # Expected price and stop-loss levels
        exp_return_pct = round(comp_score * float(metrics.get("volatility_ann", 20.0)) * (predict_bars / 252.0), 2)
        target_price = round(last_price * (1.0 + exp_return_pct / 100.0), 2)

        sl_price = None
        if direction == 1:
            sl_price = round(last_price - (atr_stop_loss_mult * atr_val), 2)
        elif direction == -1:
            sl_price = round(last_price + (atr_stop_loss_mult * atr_val), 2)

        direction_label = "NEUTRAL / HOLD"
        if direction == 1:
            direction_label = "BUY / LONG (Очікується ріст)"
        elif direction == -1:
            direction_label = "SELL / SHORT (Очікується спад)"

        return {
            "success": True,
            "as_of_date": last_date,
            "last_price": round(last_price, 2),
            "forecast_horizon_bars": predict_bars,
            "predicted_direction": direction,
            "direction_label": direction_label,
            "composite_score": comp_score,
            "recommended_position_size": pos_size,
            "expected_return_pct": exp_return_pct,
            "target_price": target_price,
            "suggested_stop_loss_price": sl_price,
            "atr_dollars": atr_val,
            "atr_pct": atr_pct,
            "chop_index": metrics.get("chop_index"),
            "reason": eval_res["reason"],
            "factor_breakdown": factor_scores,
            "quant_metrics": {
                "zscore": metrics.get("zscore"),
                "ar1_w": metrics.get("ar1_w"),
                "hurst": metrics.get("hurst"),
                "half_life": metrics.get("half_life"),
                "slope": metrics.get("slope"),
                "fast_slope": metrics.get("fast_slope"),
                "delta_slope": metrics.get("delta_slope"),
                "r2": metrics.get("r2"),
                "volatility_ann": metrics.get("volatility_ann")
            }
        }


class PortfolioWalkForwardBacktester:
    """
    Simultaneous Multi-Asset Portfolio Ensemble Walk-Forward Backtester.
    Allocates capital across multiple tickers with Fractional Kelly risk weighting.
    """

    @classmethod
    def run_portfolio_walk_forward(
        cls,
        data_dict: Dict[str, pd.DataFrame],
        train_bars: int = 60,
        predict_bars: int = 15,
        step_bars: int = 15,
        w_mean_revert: float = 0.15,
        w_momentum: float = 0.60,
        w_ar1: float = 0.15,
        w_curv: float = 0.10,
        threshold_up: float = 0.18,
        threshold_down: float = -0.18,
        sizing_mode: str = "kelly",
        fee_pct: float = 0.05,
        atr_stop_loss_mult: float = 2.0
    ) -> Dict[str, Any]:
        """Runs synchronized walk-forward across multiple asset streams."""
        tickers = list(data_dict.keys())
        if not tickers:
            return {"success": False, "error": "Порожній список активів"}

        asset_results = {}
        for t in tickers:
            df = data_dict[t]
            bt = WalkForwardBacktester(df)
            res = bt.run_multi_factor_walk_forward(
                train_bars=train_bars,
                predict_bars=predict_bars,
                step_bars=step_bars,
                w_mean_revert=w_mean_revert,
                w_momentum=w_momentum,
                w_ar1=w_ar1,
                w_curv=w_curv,
                threshold_up=threshold_up,
                threshold_down=threshold_down,
                sizing_mode=sizing_mode,
                fee_pct=fee_pct,
                atr_stop_loss_mult=atr_stop_loss_mult
            )
            asset_results[t] = res

        # Equal-weighted portfolio blend
        all_dates = set()
        for t, res in asset_results.items():
            for eq in res.get("equity_curve", []):
                all_dates.add(eq["date"])
        sorted_dates = sorted(list(all_dates))

        portfolio_curve = []
        portfolio_equity = 100.0
        n_assets = len(tickers)

        for d in sorted_dates:
            eq_vals = []
            bh_vals = []
            for t in tickers:
                matches = [c for c in asset_results[t].get("equity_curve", []) if c["date"] == d]
                if matches:
                    eq_vals.append(matches[0]["strategy_equity"])
                    bh_vals.append(matches[0]["buy_hold_equity"])
                else:
                    eq_vals.append(100.0)
                    bh_vals.append(100.0)

            mean_eq = float(np.mean(eq_vals)) if eq_vals else 100.0
            mean_bh = float(np.mean(bh_vals)) if bh_vals else 100.0

            portfolio_curve.append({
                "date": d,
                "strategy_equity": round(mean_eq, 2),
                "buy_hold_equity": round(mean_bh, 2)
            })

        # Portfolio aggregate metrics
        total_trades = sum(r.get("active_trades", 0) for r in asset_results.values())
        correct_trades = sum(r.get("correct_trades", 0) for r in asset_results.values())
        accuracy = (correct_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        ev_weighted = float(np.mean([r.get("expected_value_pct", 0.0) for r in asset_results.values()]))
        sharpe_mean = float(np.mean([r.get("sharpe_ratio", 0.0) for r in asset_results.values()]))
        sortino_mean = float(np.mean([r.get("sortino_ratio", 0.0) for r in asset_results.values()]))
        tot_return = portfolio_curve[-1]["strategy_equity"] - 100.0 if portfolio_curve else 0.0
        bh_return = portfolio_curve[-1]["buy_hold_equity"] - 100.0 if portfolio_curve else 0.0

        equities = [c["strategy_equity"] for c in portfolio_curve]
        peak = 100.0
        max_dd = 0.0
        for eq in equities:
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = ((peak - eq) / peak) * 100.0
                if dd > max_dd:
                    max_dd = dd

        return {
            "success": True,
            "portfolio_assets": tickers,
            "total_trades": total_trades,
            "correct_trades": correct_trades,
            "accuracy_pct": round(accuracy, 2),
            "expected_value_pct": round(ev_weighted, 3),
            "sharpe_ratio": round(sharpe_mean, 2),
            "sortino_ratio": round(sortino_mean, 2),
            "total_return_pct": round(tot_return, 2),
            "buy_and_hold_return_pct": round(bh_return, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "asset_breakdown": {t: {
                "trades": r.get("active_trades"),
                "accuracy": r.get("accuracy_pct"),
                "ev": r.get("expected_value_pct"),
                "sharpe": r.get("sharpe_ratio"),
                "return": r.get("total_return_pct"),
                "max_dd": r.get("max_drawdown_pct")
            } for t, r in asset_results.items()},
            "equity_curve": portfolio_curve
        }
