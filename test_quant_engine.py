import pandas as pd
from data_manager import DataManager
from backtester import WalkForwardBacktester
from math_engine import MathEngine

dm = DataManager()
df = dm.get_data_slice("AAPL")
bt = WalkForwardBacktester(df)

print("=== 1. TESTING QUANT BACKTEST WITH MEAN REVERSION (AR1_w < 0 & ZSCORE) ===")
res1 = bt.run_walk_forward(
    train_bars=60, predict_bars=15, step_bars=15,
    condition_up="zscore < -1.5 and ar1_w < 0",
    condition_down="zscore > 1.5 and ar1_w < 0",
    sizing_mode="tanh"
)
print("Res 1 - Accuracy:", res1["accuracy_pct"], "% | EV:", res1["expected_value_pct"], "% | Sharpe:", res1["sharpe_ratio"], "| Sortino:", res1["sortino_ratio"], "| Calmar:", res1["calmar_ratio"])

print("\n=== 2. TESTING QUANT BACKTEST WITH MOMENTUM (HURST > 0.5 & SLOPE > 0) ===")
res2 = bt.run_walk_forward(
    train_bars=60, predict_bars=20, step_bars=20,
    condition_up="hurst > 0.52 and slope > 0.05 and r2 > 0.4",
    condition_down="hurst > 0.52 and slope < -0.05 and r2 > 0.4",
    sizing_mode="kelly"
)
print("Res 2 - Accuracy:", res2["accuracy_pct"], "% | EV:", res2["expected_value_pct"], "% | Sharpe:", res2["sharpe_ratio"], "| Sortino:", res2["sortino_ratio"], "| Total Return:", res2["total_return_pct"], "%")

print("\n=== 3. TESTING API INTEGRATION ===")
import app
client = app.app.test_client()
r_vars = client.get("/api/math-variables")
print("Math variables available in API:", len(r_vars.get_json()))
r_bt = client.post("/api/run-backtest", json={
    "ticker": "AAPL",
    "train_bars": 60,
    "predict_bars": 15,
    "step_bars": 15,
    "condition_up": "zscore < -1.5",
    "condition_down": "zscore > 1.5",
    "sizing_mode": "hardtanh"
})
print("Backtest API Status:", r_bt.status_code, "EV:", r_bt.get_json().get("expected_value_pct"))
