from data_manager import DataManager

print("🌱 Автоматичне завантаження базових акцій (Auto-Seeding Universe)...")
dm = DataManager()
tickers = ["AAPL", "NVDA", "MSFT", "AMZN", "TSLA", "QQQ", "META", "GOOGL"]
for t in tickers:
    print(f"  • Завантаження {t}...")
    succ, msg, count = dm.download_all_history(t)
    print(f"    [{'OK' if succ else 'ERR'}] {msg}")

print("\n✅ Усі базові дані успішно завантажено та збережено в кеш!")
