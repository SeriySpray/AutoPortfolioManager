import pandas as pd
from data_manager import DataManager
from backtester import WalkForwardBacktester, PortfolioWalkForwardBacktester

dm = DataManager()
tickers = ["AAPL", "NVDA", "MSFT", "AMZN", "QQQ"]
data_dict = {t: dm.get_data_slice(t) for t in tickers}

print("=== 1. TESTING SINGLE-ASSET WITH ATR STOP-LOSS (NVDA) ===")
bt_nvda = WalkForwardBacktester(data_dict["NVDA"])
res_sl = bt_nvda.run_multi_factor_walk_forward(
    train_bars=60, predict_bars=15, step_bars=15,
    atr_stop_loss_mult=2.0,
    use_v_reversal_breaker=True
)
print("NVDA with ATR Stop-Loss & V-Breaker -> Hit Rate:", res_sl["accuracy_pct"], "% | EV:", res_sl["expected_value_pct"], "% | Max DD:", res_sl["max_drawdown_pct"], "%")

print("\n=== 2. TESTING MULTI-ASSET PORTFOLIO ENSEMBLE (5 TICKERS) ===")
res_port = PortfolioWalkForwardBacktester.run_portfolio_walk_forward(
    data_dict=data_dict,
    train_bars=60, predict_bars=15, step_bars=15,
    atr_stop_loss_mult=2.0
)
print("Portfolio Basket -> Accuracy:", res_port["accuracy_pct"], "% | EV:", res_port["expected_value_pct"], "% | Sharpe:", res_port["sharpe_ratio"], "| Sortino:", res_port["sortino_ratio"], "| Total Return:", res_port["total_return_pct"], "% | Max DD:", res_port["max_drawdown_pct"], "%")

print("\n=== 3. TESTING API ENDPOINTS ===")
import app
client = app.app.test_client()
r_port = client.post("/api/run-portfolio-backtest", json={
    "tickers": ["AAPL", "NVDA", "MSFT"],
    "train_bars": 60,
    "predict_bars": 15,
    "atr_stop_loss_mult": 2.0
})
print("API Portfolio Status:", r_port.status_code, "Accuracy:", r_port.get_json().get("accuracy_pct"), "%")
