# 🚀 AutoPortfolioManager | Advanced Quantitative Research & Live Execution Engine

Мінімалістична квантова платформа для математичного аналізу ринку акцій, компонування альфа-факторів, суворого сліпого Walk-Forward бектестингу та цілодобового автономного виконання у реальному часі на сервері Oracle Cloud.

---

## 🏛️ Ключові можливості платформи

- **⚡ Блискавичний менеджер ринкових даних (`data_manager.py`):** Завантаження всієї історії котирувань через `yfinance` з автоматичним коригуванням сплітів та дивідендів (`auto_adjust=True`) та кешуванням у форматі Apache Parquet.
- **🔬 Чисте квантове математичне ядро (`math_engine.py`):**
  - **Авторегресія AR(1):** Розрахунок ваги лагу $w$ на лог-дохідностях (Mean Reversion $w < 0$ проти Momentum $w > 0$).
  - **Показник Херста ($H$):** Класифікація режимів ринку через масштабований розмах $R/S$ ($H < 0.5$ флет, $H > 0.5$ персистентний тренд).
  - **Модель Орнштейна-Уленбека (OU):** Розрахунок швидкості повернення $\theta$ та періоду напіврозпаду $t_{1/2} = \ln(2)/\theta$.
  - **Динамічний захист:** Average True Range (ATR), Choppiness Index (CHOP), V-Reversal Circuit Breaker.
  - **Сайзинг позицій:** Constant, HardTanh, Tanh, Fractional Kelly.
- **👁️ Строгий сліпий Walk-Forward бектестер (`backtester.py`):**
  - Послідовне ковзне вікно $[T_{\text{train}}] \to [T_{\text{predict}}]$.
  - Сліпий прогноз майбутнього без витоку даних наперед.
  - Розрахунок Expected Value $E[X]$, Sharpe, Sortino, Calmar, Max Drawdown, Win/Loss Payoff.
  - Портфельний ансамбль багатьох активів.
- **🤖 Цілодобовий демон реального часу (`live_trader_daemon.py`):**
  - 24/7 моніторинг ринку на сервері Oracle Cloud.
  - Автоматичне відкриття позицій та контроль динамічного ATR Stop-Loss.
  - Миттєві сповіщення у Telegram.
- **🥊 Комплекс стрес-тестів (`stress_test_engine.py`):**
  - Аудит на крахах 2000, 2008, 2020, 2022 років.
  - 500-ітераційний Монте-Карло тест на випадковість успіху (PBO).
  - Чутливість до комісій та проковзування.

---

## 🚀 Швидкий локальний запуск (Windows / Linux)

```bash
# 1. Встановлення залежностей
pip install -r requirements.txt

# 2. Запуск локального сервера
python app.py
```
Відкрийте у браузері: **`http://127.0.0.1:5000`**

---

## ☁️ Розгортання на сервері Oracle Cloud (1-Click)

1. Підключіться до сервера через SSH:
```bash
ssh ubuntu@<IP_СЕРВЕРА>
```
2. Склонуйте репозиторій та запустіть скрипт розгортання:
```bash
git clone https://github.com/<your-username>/AutoPortfolioManager.git
cd AutoPortfolioManager
chmod +x deploy_oracle.sh
./deploy_oracle.sh
```

---

## 📂 Структура проєкту

- `app.py` — REST API бекенд на Flask.
- `math_engine.py` — Математичні метрики, AR(1), Hurst, OU, мультифакторна модель.
- `backtester.py` — Walk-Forward бектестер та портфельний ансамбль.
- `live_trader_daemon.py` — 24/7 демон для сервера Oracle з Telegram-сповіщеннями.
- `stress_test_engine.py` — Інституційні стрес-тести та Монте-Карло аудит.
- `strategy_research_loop.py` — Автономний цикл ресерчу та еволюції моделей.
- `deploy_oracle.sh` — Скрипт 1-клік розгортання для Oracle Cloud (systemd).
- `QUANT_ADVANCED_RESEARCH.md` — Енциклопедія квантових фінансів та формул.
- `QUANT_MODEL_STRESS_TEST_REPORT.md` — Звіт про вразливості та стрес-тести.
- `CROSS_ASSET_TIMEFRAME_STUDY.md` — Дослідження на різних активах та таймфреймах.
- `STRATEGY_RESEARCH_EXPERIMENTS.md` — Журнал квантових експериментів.
