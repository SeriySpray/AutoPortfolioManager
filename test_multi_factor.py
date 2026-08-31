import pandas as pd
from data_manager import DataManager
from backtester import WalkForwardBacktester

dm = DataManager()
dm.download_all_history("AAPL")
dm.download_all_history("NVDA")
dm.download_all_history("MSFT")

df_aapl = dm.get_data_slice("AAPL")
bt_aapl = WalkForwardBacktester(df_aapl)

print("=== 1. MULTI-FACTOR WALK-FORWARD BACKTEST ON AAPL ===")
res_mf = bt_aapl.run_multi_factor_walk_forward(
    train_bars=60,
    predict_bars=15,
    step_bars=15,
    w_mean_revert=0.35,
    w_momentum=0.35,
    w_ar1=0.20,
    w_curv=0.10,
    threshold_up=0.12,
    threshold_down=-0.12,
    sizing_mode="tanh"
)
print("Total Windows:", res_mf["total_windows"])
print("Active Trades:", res_mf["active_trades"])
print("Hit Rate Accuracy:", res_mf["accuracy_pct"], "%")
print("Expected Value E[X]:", res_mf["expected_value_pct"], "%")
print("Win Rate:", res_mf["win_rate_pct"], "% | Loss Rate:", res_mf["loss_rate_pct"], "%")
print("Sharpe Ratio:", res_mf["sharpe_ratio"])
print("Sortino Ratio:", res_mf["sortino_ratio"])
print("Calmar Ratio:", res_mf["calmar_ratio"])
print("Max Drawdown:", res_mf["max_drawdown_pct"], "%")
print("Strategy Return:", res_mf["total_return_pct"], "% vs B&H:", res_mf["buy_and_hold_return_pct"], "%")

print("\n=== 2. LATEST BLIND FORECAST ON AAPL (AS OF LATEST DATE) ===")
live_fc = bt_aapl.generate_latest_blind_forecast(
    train_bars=60,
    predict_bars=15,
    w_mean_revert=0.35,
    w_momentum=0.35,
    w_ar1=0.20,
    w_curv=0.10,
    threshold_up=0.12,
    threshold_down=-0.12,
    sizing_mode="tanh"
)
print("As of date:", live_fc["as_of_date"], "| Last price:", live_fc["last_price"])
print("Forecast Direction:", live_fc["direction_label"])
print("Composite Score:", live_fc["composite_score"])
print("Position Size S:", live_fc["recommended_position_size"])
print("Expected Return %:", live_fc["expected_return_pct"], "%")
print("Target Price:", live_fc["target_price"])
print("Reason:", live_fc["reason"])
print("Factor Breakdown:", live_fc["factor_breakdown"])
print("Quant Metrics:", live_fc["quant_metrics"])

print("\n=== 3. FLASK API VERIFICATION ===")
import app
client = app.app.test_client()
r1 = client.post("/api/run-multi-factor-backtest", json={
    "ticker": "AAPL",
    "train_bars": 60,
    "predict_bars": 15,
    "step_bars": 15,
    "w_mean_revert": 0.35,
    "w_momentum": 0.35,
    "w_ar1": 0.20,
    "w_curv": 0.10,
    "threshold_up": 0.12,
    "threshold_down": -0.12,
    "sizing_mode": "tanh"
})
print("API Backtest status:", r1.status_code, "Windows:", r1.get_json().get("total_windows"))

r2 = client.post("/api/generate-live-forecast", json={
    "ticker": "AAPL",
    "train_bars": 60,
    "predict_bars": 15
})
print("API Live Forecast status:", r2.status_code, "Direction:", r2.get_json().get("direction_label"))
