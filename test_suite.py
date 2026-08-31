import pandas as pd
import numpy as np
from data_manager import DataManager
from backtester import WalkForwardBacktester
from math_models import MathModelRegistry, compute_hurst_exponent

dm = DataManager()
dm.download_all_history('MSFT')
dm.download_all_history('NVDA')
df = dm.get_data_slice('AAPL')

print("=== 1. TESTING ALL CURRENT MODELS ON AAPL ===")
for m in MathModelRegistry.AVAILABLE_MODELS:
    bt = WalkForwardBacktester(df)
    res = bt.run_walk_forward(m['id'], train_bars=60, predict_bars=20, step_bars=20, model_params=m.get('params', {}))
    print(f"Model: {m['id']:<24} | Windows: {res['total_windows']:<4} | Trades: {res['active_trades']:<4} | Acc: {res['accuracy_pct']:>5.1f}% | Ret: {res['total_return_pct']:>8.1f}% | MDD: {res['max_drawdown_pct']:>5.1f}% | Sharpe: {res['sharpe_ratio']}")

print("\n=== 2. TESTING OVERLAPPING WINDOW BUG ===")
bt = WalkForwardBacktester(df)
res_non_overlap = bt.run_walk_forward('linear_trend', 60, 20, 20)
res_overlap = bt.run_walk_forward('linear_trend', 60, 20, 5)
print(f"Non-overlapping (predict=20, step=20): Windows={res_non_overlap['total_windows']}, Strategy Return={res_non_overlap['total_return_pct']}%")
print(f"Overlapping (predict=20, step=5):     Windows={res_overlap['total_windows']}, Strategy Return={res_overlap['total_return_pct']}%")

print("\n=== 3. TESTING SPLIT ADJUSTMENT ISSUE ===")
raw_aapl = dm._get_file_path('AAPL')
aapl_df = pd.read_parquet(raw_aapl)
print("AAPL first date:", aapl_df['Date'].iloc[0], "AAPL first close:", aapl_df['Close'].iloc[0])
print("AAPL last date:", aapl_df['Date'].iloc[-1], "AAPL last close:", aapl_df['Close'].iloc[-1])

print("\n=== 4. TESTING HURST EXPONENT ESTIMATOR ===")
# Synthetic geometric brownian motion (H should be ~0.5)
np.random.seed(42)
random_walk = pd.Series(np.cumprod(1 + np.random.normal(0, 0.01, 1000)))
h_val = compute_hurst_exponent(random_walk)
print(f"Hurst exponent for pure Random Walk (expected ~0.50): Calculated = {h_val:.4f}")
