import os
import json
import time
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from data_manager import DataManager
from backtester import WalkForwardBacktester
from math_engine import MathEngine, MultiFactorModel


class StrategyResearchLab:
    """
    Autonomous Quantitative Strategy Research & Blind Walk-Forward Testing Lab.
    Systematically proposes hypotheses, executes blind walk-forward validation,
    analyzes failures, adapts tactics, and tracks results.
    """

    def __init__(self, tickers: List[str] = ["AAPL", "NVDA", "MSFT", "AMZN", "SPY"]):
        self.tickers = tickers
        self.dm = DataManager()
        self.results_log: List[Dict[str, Any]] = []
        self._ensure_data_downloaded()

    def _ensure_data_downloaded(self):
        print("📥 Завантаження та підготовка ринкових даних для тест-всесвіту...")
        for ticker in self.tickers:
            success, msg, count = self.dm.download_all_history(ticker)
            print(f"  • {ticker}: {count} свічок")

    def run_hypothesis_backtest(
        self,
        name: str,
        hypothesis_desc: str,
        ticker: str,
        train_bars: int,
        predict_bars: int,
        step_bars: int,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Runs blind walk-forward test for a specific hypothesis on a ticker."""
        df = self.dm.get_data_slice(ticker)
        if df is None or len(df) < (train_bars + predict_bars):
            return {"success": False, "error": "Недостатньо даних"}

        bt = WalkForwardBacktester(df)
        
        is_mf = config.get("is_multi_factor", True)
        if is_mf:
            res = bt.run_multi_factor_walk_forward(
                train_bars=train_bars,
                predict_bars=predict_bars,
                step_bars=step_bars,
                w_mean_revert=config.get("w_mean_revert", 0.35),
                w_momentum=config.get("w_momentum", 0.35),
                w_ar1=config.get("w_ar1", 0.20),
                w_curv=config.get("w_curv", 0.10),
                threshold_up=config.get("threshold_up", 0.15),
                threshold_down=config.get("threshold_down", -0.15),
                sizing_mode=config.get("sizing_mode", "tanh")
            )
        else:
            res = bt.run_walk_forward(
                train_bars=train_bars,
                predict_bars=predict_bars,
                step_bars=step_bars,
                condition_up=config.get("condition_up", ""),
                condition_down=config.get("condition_down", ""),
                sizing_mode=config.get("sizing_mode", "constant")
            )

        res["hypothesis_name"] = name
        res["hypothesis_desc"] = hypothesis_desc
        res["ticker"] = ticker
        res["config"] = config
        res["is_profitable"] = (res["expected_value_pct"] > 0 and res["profit_factor"] > 1.1)
        return res

    def run_autonomous_evolution_cycle(self) -> List[Dict[str, Any]]:
        """
        Executes an iterative strategy design and testing loop:
        Proposes tactics -> Blind Walk-Forward Backtests -> Analyzes failures -> Adapts parameters.
        """
        print("\n🚀 ЗАПУСК БЕЗПЕРЕРВНОГО ЦИКЛУ КВАНТОВОГО РЕСЕРЧУ ТА СЛІПОГО БЕКТЕСТУ...")
        
        experiment_queue = [
            # TACTIC 1: Pure Mean Reversion (Z-Score + OU Half Life)
            {
                "name": "Тактика 1.0: Екстремальне повернення до середнього (Z-Score Reversion)",
                "desc": "Вхід при сильних статистичних відхиленнях (Z-Score > |1.8|) з очікуванням відкату.",
                "ticker": "AAPL",
                "train_bars": 60, "predict_bars": 10, "step_bars": 10,
                "config": {
                    "is_multi_factor": False,
                    "condition_up": "zscore < -1.8 and half_life < 15.0",
                    "condition_down": "zscore > 1.8 and half_life < 15.0",
                    "sizing_mode": "tanh"
                }
            },
            # TACTIC 2: Pure Momentum (Hurst Trend Filter + Linear Slope)
            {
                "name": "Тактика 2.0: Персистентний імпульс за показником Херста (Hurst Momentum)",
                "desc": "Фільтрація виключно трендових режимів (H > 0.53) з підтвердженням якості регресії R² > 0.4.",
                "ticker": "NVDA",
                "train_bars": 60, "predict_bars": 15, "step_bars": 15,
                "config": {
                    "is_multi_factor": False,
                    "condition_up": "hurst > 0.53 and slope > 0.08 and r2 > 0.4",
                    "condition_down": "hurst > 0.53 and slope < -0.08 and r2 > 0.4",
                    "sizing_mode": "tanh"
                }
            },
            # TACTIC 3: Econometric Autoregression AR(1) Serial Inertia
            {
                "name": "Тактика 3.0: Авторегресійна інерція AR(1) з волатильнісним фільтром",
                "desc": "Використання знаку та величини ваги лагу AR(1) w для визначення інерції ціни.",
                "ticker": "MSFT",
                "train_bars": 90, "predict_bars": 15, "step_bars": 15,
                "config": {
                    "is_multi_factor": False,
                    "condition_up": "ar1_w > 0.15 and slope > 0.05 and volatility_ann < 35.0",
                    "condition_down": "ar1_w > 0.15 and slope < -0.05 and volatility_ann < 35.0",
                    "sizing_mode": "kelly"
                }
            },
            # TACTIC 4: Multi-Factor Composite (Equal Weights)
            {
                "name": "Тактика 4.0: Базовий мультифакторний композит (Equal Weights)",
                "desc": "Комбінування Mean Reversion (0.35), Momentum (0.35), AR(1) (0.20) та Curvature (0.10).",
                "ticker": "SPY",
                "train_bars": 60, "predict_bars": 15, "step_bars": 15,
                "config": {
                    "is_multi_factor": True,
                    "w_mean_revert": 0.35, "w_momentum": 0.35, "w_ar1": 0.20, "w_curv": 0.10,
                    "threshold_up": 0.12, "threshold_down": -0.12,
                    "sizing_mode": "tanh"
                }
            },
            # TACTIC 5: Adaptive Regime-Shifted Multi-Factor (Momentum-Heavy for Growth Stocks)
            {
                "name": "Тактика 5.0: Адаптивний мультифактор з акцентом на тренд (Momentum-Biased)",
                "desc": "Підсилення ваги Momentum до 0.60 та зниження ваги Mean Reversion для сильних акцій росту.",
                "ticker": "NVDA",
                "train_bars": 60, "predict_bars": 20, "step_bars": 20,
                "config": {
                    "is_multi_factor": True,
                    "w_mean_revert": 0.15, "w_momentum": 0.60, "w_ar1": 0.15, "w_curv": 0.10,
                    "threshold_up": 0.18, "threshold_down": -0.18,
                    "sizing_mode": "kelly"
                }
            },
            # TACTIC 6: Asymmetric Volatility Reversal with Fractional Kelly
            {
                "name": "Тактика 6.0: Асиметричний відкат з низькою волатильністю (Low-Vol Reversal)",
                "desc": "Купівля перепроданості лише у спокійних ринкових режимах (волатильність < 25%).",
                "ticker": "AAPL",
                "train_bars": 60, "predict_bars": 15, "step_bars": 15,
                "config": {
                    "is_multi_factor": False,
                    "condition_up": "zscore < -1.4 and volatility_ann < 28.0 and window_sortino > -0.5",
                    "condition_down": "zscore > 1.6 and volatility_ann < 28.0",
                    "sizing_mode": "kelly"
                }
            },
            # TACTIC 7: Multi-Factor Conservative (High Threshold Filters)
            {
                "name": "Тактика 7.0: Консервативний мультифактор з високим порогом входу (High-Conviction)",
                "desc": "Вхід лише при сильному консенсусі факторів (Threshold > |0.25|) для максимізації EV.",
                "ticker": "AMZN",
                "train_bars": 90, "predict_bars": 20, "step_bars": 20,
                "config": {
                    "is_multi_factor": True,
                    "w_mean_revert": 0.30, "w_momentum": 0.40, "w_ar1": 0.20, "w_curv": 0.10,
                    "threshold_up": 0.25, "threshold_down": -0.25,
                    "sizing_mode": "tanh"
                }
            },
            # TACTIC 8: Curvature / Polynomial Acceleration Reversals
            {
                "name": "Тактика 8.0: Поліноміальне прискорення та виснаження тренду (Curvature Exhaustion)",
                "desc": "Виявлення сповільнення тренду через зміну знаку 2-ї похідної (Curvature).",
                "ticker": "MSFT",
                "train_bars": 45, "predict_bars": 10, "step_bars": 10,
                "config": {
                    "is_multi_factor": False,
                    "condition_up": "curvature > 0.00005 and zscore < -0.5 and slope < 0",
                    "condition_down": "curvature < -0.00005 and zscore > 0.5 and slope > 0",
                    "sizing_mode": "hardtanh"
                }
            }
        ]

        evaluated_results = []

        for idx, exp in enumerate(experiment_queue, 1):
            print(f"\n==================================================")
            print(f"🧪 [ЕКСПЕРИМЕНТ {idx}/{len(experiment_queue)}] {exp['name']}")
            print(f"📋 Гіпотеза: {exp['desc']}")
            print(f"🎯 Актив: {exp['ticker']} | Вікна: Train={exp['train_bars']}b, Predict={exp['predict_bars']}b, Step={exp['step_bars']}b")

            res = self.run_hypothesis_backtest(
                name=exp["name"],
                hypothesis_desc=exp["desc"],
                ticker=exp["ticker"],
                train_bars=exp["train_bars"],
                predict_bars=exp["predict_bars"],
                step_bars=exp["step_bars"],
                config=exp["config"]
            )

            if not res.get("success"):
                print(f"❌ Помилка тестування: {res.get('error')}")
                continue

            status = "✅ ПРИБУТКОВА" if res["is_profitable"] else "❌ НЕПРИБУТКОВА (ПОТРІБНА АДАПТАЦІЯ)"
            print(f"📊 Результат сліпого бектесту: {status}")
            print(f"   • Всього сліпих вікон: {res['total_windows']} | Активних угод: {res['active_trades']}")
            print(f"   • Точність (Hit Rate): {res['accuracy_pct']}% | Win Rate: {res['win_rate_pct']}%")
            print(f"   • Мат. Очікування (EV): {res['expected_value_pct']:+.3f}% на угоду")
            print(f"   • Sharpe Ratio: {res['sharpe_ratio']} | Sortino: {res['sortino_ratio']} | Calmar: {res['calmar_ratio']}")
            print(f"   • Дохідність моделі: {res['total_return_pct']:+.2f}% | Max Drawdown: -{res['max_drawdown_pct']}% | Profit Factor: {res['profit_factor']}")

            # ADAPTATION STEP IF UNPROFITABLE
            if not res["is_profitable"]:
                print(f"⚙️ ─── АДАПТАЦІЯ ТАКТИКИ (ЗМІНА СТРАТЕГІЇ) ───")
                adapted_config = dict(exp["config"])
                adapted_name = f"{exp['name']} [Адаптована v2]"
                
                # Adaptation heuristics:
                # 1. If EV < 0, widen filters (higher threshold or tighter predicate)
                # 2. Switch to Fractional Kelly sizing to damp drawdowns
                # 3. Increase training window size
                if exp["config"].get("is_multi_factor"):
                    adapted_config["threshold_up"] = round(adapted_config.get("threshold_up", 0.15) * 1.5, 2)
                    adapted_config["threshold_down"] = round(adapted_config.get("threshold_down", -0.15) * 1.5, 2)
                    adapted_config["sizing_mode"] = "kelly"
                else:
                    adapted_config["sizing_mode"] = "kelly"
                
                adapted_train = exp["train_bars"] + 30
                print(f"   🔄 Збільшено In-Sample вікно до {adapted_train}b, перехід на Fractional Kelly та підвищення фільтрів.")

                res_adapt = self.run_hypothesis_backtest(
                    name=adapted_name,
                    hypothesis_desc=f"Адаптація після виявлення просідань: {exp['desc']}",
                    ticker=exp["ticker"],
                    train_bars=adapted_train,
                    predict_bars=exp["predict_bars"],
                    step_bars=exp["step_bars"],
                    config=adapted_config
                )

                if res_adapt.get("success"):
                    adapt_status = "✅ ПРИБУТКОВА" if res_adapt["is_profitable"] else "⚠️ ПОКРАЩЕНА / НЕЙТРАЛЬНА"
                    print(f"   📈 Результат після адаптації: {adapt_status} (EV: {res_adapt['expected_value_pct']:+.3f}%, Sharpe: {res_adapt['sharpe_ratio']}, Ret: {res_adapt['total_return_pct']:+.2f}%)")
                    evaluated_results.append(res_adapt)

            evaluated_results.append(res)

        self.results_log = evaluated_results
        self._save_research_log_to_markdown()
        return evaluated_results

    def _save_research_log_to_markdown(self):
        """Generates comprehensive markdown report of all experiment results."""
        lines = [
            "# 🧪 Журнал Автономного Квантового Ресерчу та Сліпих Бектестів",
            f"*Останнє оновлення: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n",
            "---",
            "## 📊 Зведена таблиця результатів експериментів\n",
            "| # | Назва тактики | Тікер | Угод | Точність | EV (%/угода) | Sharpe | Sortino | Дохідність (%) | Max DD (%) | Profit Factor | Статус |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"
        ]

        sorted_res = sorted(self.results_log, key=lambda x: (x.get("expected_value_pct", -999), x.get("sharpe_ratio", -999)), reverse=True)

        for i, r in enumerate(sorted_res, 1):
            status = "🟢 Прибуткова" if r.get("is_profitable") else "🔴 Неприбуткова"
            ev = f"{r.get('expected_value_pct', 0.0):+.3f}%"
            ret = f"{r.get('total_return_pct', 0.0):+.1f}%"
            lines.append(
                f"| {i} | **{r.get('hypothesis_name', '')}** | `{r.get('ticker', '')}` | {r.get('active_trades', 0)} | {r.get('accuracy_pct', 0.0)}% | {ev} | {r.get('sharpe_ratio', 0.0)} | {r.get('sortino_ratio', 0.0)} | {ret} | -{r.get('max_drawdown_pct', 0.0)}% | {r.get('profit_factor', 0.0)} | {status} |"
            )

        lines.extend([
            "\n---\n",
            "## 🔬 Детальний розбір гіпотез та висновки\n"
        ])

        for i, r in enumerate(sorted_res, 1):
            lines.extend([
                f"### {i}. {r.get('hypothesis_name', '')}",
                f"- **Опис гіпотези:** {r.get('hypothesis_desc', '')}",
                f"- **Тікер:** `{r.get('ticker', '')}`",
                f"- **Параметри конфігурації:** `{json.dumps(r.get('config', {}), ensure_ascii=False)}`",
                f"- **Результати Out-of-Sample валідації:**",
                f"  - Точність напрямку (Hit Rate): **{r.get('accuracy_pct')}%** ({r.get('correct_trades')}/{r.get('active_trades')} вірно)",
                f"  - Математичне очікування P&L ($E[X]$): **{r.get('expected_value_pct'):+.3f}%** на угоду",
                f"  - Win Rate / Loss Rate: **{r.get('win_rate_pct')}% / {r.get('loss_rate_pct')}%** (Співвідношення Win/Loss: **{r.get('win_loss_payoff')}**)",
                f"  - Коефіцієнт Шарпа: **{r.get('sharpe_ratio')}** | Сортіно: **{r.get('sortino_ratio')}** | Кальмара: **{r.get('calmar_ratio')}**",
                f"  - Загальна дохідність: **{r.get('total_return_pct'):+.2f}%** (Benchmark B&H: {r.get('buy_and_hold_return_pct'):+.2f}%)",
                f"  - Максимальне просідання: **-{r.get('max_drawdown_pct')}%**",
                f"- **Аналітичний висновок:** {'Стратегія демонструє стабільну позитивну статистичну перевагу (+EV) та стійкість до ринкових коливань.' if r.get('is_profitable') else 'Стратегія має високий шум або деградує при зміні ринкового режиму. Необхідне звуження порогу фільтрації або коригування ваг факторів.'}\n"
            ])

        with open("STRATEGY_RESEARCH_EXPERIMENTS.md", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print("💾 Збережено повний звіт у STRATEGY_RESEARCH_EXPERIMENTS.md")


if __name__ == "__main__":
    lab = StrategyResearchLab()
    lab.run_autonomous_evolution_cycle()
