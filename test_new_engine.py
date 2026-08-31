import pandas as pd
from data_manager import DataManager
from backtester import WalkForwardBacktester
from math_engine import MathEngine, safe_eval_condition, compute_window_math_metrics

dm = DataManager()
dm.download_all_history("AAPL")
dm.download_all_history("MSFT")
dm.download_all_history("NVDA")

df_aapl = dm.get_data_slice("AAPL")
df_nvda = dm.get_data_slice("NVDA")

print("=== 1. TESTING MATH ENGINE ISOLATED WINDOW METRICS ===")
sample_slice = df_aapl.iloc[0:60]
metrics = compute_window_math_metrics(sample_slice)
print("Keys computed on 60-bar window:", list(metrics.keys()))
print("Sample values: ZScore =", metrics["zscore"], "Slope =", metrics["slope"], "R2 =", metrics["r2"], "Vol =", metrics["volatility_ann"])

print("\n=== 2. TESTING SAFE CONDITION EVALUATOR ===")
print("Eval 'zscore < 0':", safe_eval_condition("zscore < 0", metrics))
print("Eval 'slope > 0.05 and r2 > 0.4':", safe_eval_condition("slope > 0.05 and r2 > 0.4", metrics))
print("Eval invalid syntax:", safe_eval_condition("zscore <<<>", metrics))

print("\n=== 3. TESTING WALK-FORWARD BACKTEST ON AAPL WITH PURE MATH FORMULAS ===")
bt_aapl = WalkForwardBacktester(df_aapl)

# Test 1: Z-Score Mean Reversion (Buy when zscore < -1.5, Sell when zscore > 1.5)
res1 = bt_aapl.run_walk_forward(
    train_bars=60, predict_bars=15, step_bars=15,
    condition_up="zscore < -1.5",
    condition_down="zscore > 1.5"
)
print(f"Test 1 (Z-Score Reversion): Total Windows={res1['total_windows']} | Active={res1['active_trades']} | Acc={res1['accuracy_pct']}% | Ret={res1['total_return_pct']}% | MDD={res1['max_drawdown_pct']}% | Sharpe={res1['sharpe_ratio']}")

# Test 2: Linear Trend Momentum (Buy when slope > 0.08 and r2 > 0.45, Sell when slope < -0.08 and r2 > 0.45)
res2 = bt_aapl.run_walk_forward(
    train_bars=60, predict_bars=20, step_bars=20,
    condition_up="slope > 0.08 and r2 > 0.45",
    condition_down="slope < -0.08 and r2 > 0.45"
)
print(f"Test 2 (Linear Momentum):  Total Windows={res2['total_windows']} | Active={res2['active_trades']} | Acc={res2['accuracy_pct']}% | Ret={res2['total_return_pct']}% | MDD={res2['max_drawdown_pct']}% | Sharpe={res2['sharpe_ratio']}")

# Test 3: Complex Multi-Metric Formula (Buy when oversold with low volatility)
res3 = bt_aapl.run_walk_forward(
    train_bars=60, predict_bars=15, step_bars=15,
    condition_up="zscore < -1.2 and volatility_ann < 35.0",
    condition_down="zscore > 1.2 and volatility_ann > 40.0"
)
print(f"Test 3 (Multi-Metric):      Total Windows={res3['total_windows']} | Active={res3['active_trades']} | Acc={res3['accuracy_pct']}% | Ret={res3['total_return_pct']}% | MDD={res3['max_drawdown_pct']}% | Sharpe={res3['sharpe_ratio']}")

print("\n=== 4. TESTING NVDA (ACROSS SPLITS) ===")
bt_nvda = WalkForwardBacktester(df_nvda)
res_nvda = bt_nvda.run_walk_forward(
    train_bars=60, predict_bars=20, step_bars=20,
    condition_up="slope > 0.1 and r2 > 0.5",
    condition_down="slope < -0.1 and r2 > 0.5"
)
print(f"NVDA Momentum: Total Windows={res_nvda['total_windows']} | Active={res_nvda['active_trades']} | Acc={res_nvda['accuracy_pct']}% | Ret={res_nvda['total_return_pct']}% | B&H={res_nvda['buy_and_hold_return_pct']}%")

print("\n=== 5. TESTING FLASK API TEST CLIENT ===")
import app
client = app.app.test_client()
r_vars = client.get("/api/math-variables")
print("Math variables status:", r_vars.status_code, "Count:", len(r_vars.get_json()))
r_bt = client.post("/api/run-backtest", json={
    "ticker": "AAPL",
    "train_bars": 60,
    "predict_bars": 15,
    "step_bars": 15,
    "condition_up": "zscore < -1.5",
    "condition_down": "zscore > 1.5"
})
print("Backtest API status:", r_bt.status_code, "Success:", r_bt.get_json().get("success"))
