from data_manager import DataManager
import time

print("🌱 Автоматичне швидке завантаження базових акцій (10y OHLCV)...")
dm = DataManager()
tickers = ["AAPL", "NVDA", "MSFT", "AMZN", "TSLA", "QQQ", "META", "GOOGL"]

for t in tickers:
    t0 = time.time()
    succ, msg, count = dm.download_all_history(t)
    dt = round(time.time() - t0, 2)
    status = "✅ OK" if succ else "❌ ERR"
    print(f"  {status} [{t}] {count} свічок за {dt}s")

print("\n🎉 Усі базові дані успішно завантажено та збережено в кеш!")
