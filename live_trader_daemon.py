import os
import time
import json
import sqlite3
import datetime
import requests
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from data_manager import DataManager
from math_engine import MathEngine, MultiFactorModel


class LiveQuantDaemon:
    """
    Ultra-lightweight 24/7 Real-Time Quantitative Trading & Signal Daemon.
    Optimized for low-RAM cloud VPS instances (e.g. 1GB RAM Oracle VMs).
    Pre-computes alpha scanner metrics directly into SQLite to keep Web API instant.
    """

    def __init__(
        self,
        tickers: List[str] = ["AAPL", "NVDA", "MSFT", "AMZN", "TSLA", "QQQ", "META", "GOOGL"],
        poll_interval_seconds: int = 120,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        db_path: str = "live_portfolio.db"
    ):
        self.tickers = tickers
        self.poll_interval = poll_interval_seconds
        self.tg_token = telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.tg_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.db_path = db_path
        self.dm = DataManager()
        self.is_running = False
        self._init_db()

    def _init_db(self):
        """Initializes SQLite database for tracking live positions, trade logs, and scanner cache."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                ticker TEXT PRIMARY KEY,
                direction INTEGER,
                size REAL,
                entry_price REAL,
                entry_date TEXT,
                atr_sl_price REAL,
                target_price REAL,
                composite_score REAL,
                unrealized_pnl_pct REAL,
                updated_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                direction INTEGER,
                size REAL,
                entry_price REAL,
                exit_price REAL,
                entry_date TEXT,
                exit_date TEXT,
                pnl_pct REAL,
                exit_reason TEXT,
                created_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS live_system_status (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS scanner_cache (
                ticker TEXT PRIMARY KEY,
                price REAL,
                composite_score REAL,
                signal TEXT,
                hurst REAL,
                slope REAL,
                atr_pct REAL,
                chop_index REAL,
                status TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def send_notification(self, message: str):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{ts}] {message}"
        print(formatted, flush=True)

        if self.tg_token and self.tg_chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
                payload = {
                    "chat_id": self.tg_chat_id,
                    "text": f"🤖 *AUTOPORTFOLIO LIVE ALERT*\n`{formatted}`",
                    "parse_mode": "Markdown"
                }
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                print(f"⚠️ Telegram notification error: {e}", flush=True)

    def update_system_status(self, status: str, active_positions: int):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cur.execute("INSERT OR REPLACE INTO live_system_status (key, value, updated_at) VALUES ('status', ?, ?)", (status, now))
        cur.execute("INSERT OR REPLACE INTO live_system_status (key, value, updated_at) VALUES ('active_positions', ?, ?)", (str(active_positions), now))
        cur.execute("INSERT OR REPLACE INTO live_system_status (key, value, updated_at) VALUES ('last_heartbeat', ?, ?)", (now, now))
        conn.commit()
        conn.close()

    def process_ticker_live_tick(self, ticker: str):
        succ, msg, count = self.dm.download_all_history(ticker)
        df = self.dm.get_data_slice(ticker, auto_download=False)
        if df is None or len(df) < 30:
            return

        last_row = df.iloc[-1]
        current_price = round(float(last_row["Close"]), 2)
        current_date = last_row["Date"].strftime("%Y-%m-%d")

        train_slice = df.iloc[-60:]
        eval_res = MathEngine.evaluate_multi_factor_window(
            train_df=train_slice,
            w_mean_revert=0.15,
            w_momentum=0.60,
            w_ar1=0.15,
            w_curv=0.10,
            threshold_up=0.18,
            threshold_down=-0.18,
            sizing_mode="kelly",
            use_chop_filter=True,
            use_v_reversal_breaker=True
        )

        direction = eval_res["direction"]
        comp_score = eval_res["composite_score"]
        pos_size = eval_res["position_size"]
        metrics = eval_res["metrics"]
        atr_val = float(metrics.get("atr_val", 2.0))
        atr_pct = float(metrics.get("atr_pct", 2.5))
        hurst = float(metrics.get("hurst", 0.5))
        slope = float(metrics.get("slope", 0.0))
        chop = float(metrics.get("chop_index", 50.0))

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("SELECT ticker, direction, size, entry_price, entry_date, atr_sl_price, target_price FROM positions WHERE ticker=?", (ticker,))
        pos = cur.fetchone()

        status_text = "У ПОЗИЦІЇ" if pos else "МОНІТОРИНГ"
        sig_label = "LONG" if direction == 1 else ("SHORT" if direction == -1 else "NEUTRAL")

        # Update scanner cache in SQLite
        now = datetime.datetime.now().isoformat()
        cur.execute("""
            INSERT OR REPLACE INTO scanner_cache (ticker, price, composite_score, signal, hurst, slope, atr_pct, chop_index, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, current_price, comp_score, sig_label, hurst, slope, atr_pct, chop, status_text, now))

        # Position Management
        if pos:
            _, p_dir, p_size, p_entry, p_date, p_sl, p_target = pos
            pnl_pct = ((current_price - p_entry) / p_entry * 100.0) if p_dir == 1 else ((p_entry - current_price) / p_entry * 100.0)

            sl_triggered = False
            if p_dir == 1 and p_sl and current_price <= p_sl:
                sl_triggered = True
            elif p_dir == -1 and p_sl and current_price >= p_sl:
                sl_triggered = True

            signal_reversed = (p_dir == 1 and direction == -1) or (p_dir == -1 and direction == 1)

            if sl_triggered or signal_reversed:
                exit_reason = "ATR Stop-Loss захист" if sl_triggered else "Розворот квантового сигналу"
                realized_pnl = round(pnl_pct * abs(p_size), 2)

                cur.execute("""
                    INSERT INTO trade_history (ticker, direction, size, entry_price, exit_price, entry_date, exit_date, pnl_pct, exit_reason, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ticker, p_dir, p_size, p_entry, current_price, p_date, current_date, realized_pnl, exit_reason, now))

                cur.execute("DELETE FROM positions WHERE ticker=?", (ticker,))
                conn.commit()

                self.send_notification(
                    f"🔴 ЗАКРИТО ПОЗИЦІЮ [{ticker}]: {exit_reason}\n"
                    f"   • Вхід: ${p_entry} -> Вихід: ${current_price}\n"
                    f"   • Результат: {realized_pnl:+0.2f}%"
                )
            else:
                cur.execute("UPDATE positions SET unrealized_pnl_pct=?, updated_at=? WHERE ticker=?", (round(pnl_pct * abs(p_size), 2), now, ticker))
                conn.commit()

        elif direction != 0:
            sl_price = round(current_price - (2.0 * atr_val), 2) if direction == 1 else round(current_price + (2.0 * atr_val), 2)
            target_p = round(current_price * (1.0 + (comp_score * 0.05)), 2)

            cur.execute("""
                INSERT INTO positions (ticker, direction, size, entry_price, entry_date, atr_sl_price, target_price, composite_score, unrealized_pnl_pct, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?)
            """, (ticker, direction, pos_size, current_price, current_date, sl_price, target_p, comp_score, now))
            conn.commit()

            dir_text = "🟢 ВХІД У LONG (BUY)" if direction == 1 else "🔻 ВХІД У SHORT (SELL)"
            self.send_notification(
                f"{dir_text} [{ticker}]\n"
                f"   • Поточна ціна: ${current_price}\n"
                f"   • Сайзинг: S = {pos_size}\n"
                f"   • Динамічний Stop-Loss: ${sl_price}\n"
                f"   • Composite Score: {comp_score:+0.3f}\n"
                f"   • Обґрунтування: {eval_res['reason']}"
            )

        conn.commit()
        conn.close()

    def run_live_cycle(self):
        self.is_running = True
        self.send_notification("🚀 Квантовий демон успішно запущено на сервері Oracle! Моніторинг активів розпочато.")

        while self.is_running:
            try:
                conn = sqlite3.connect(self.db_path)
                cur = conn.cursor()
                cur.execute("SELECT count(*) FROM positions")
                active_pos_count = cur.fetchone()[0]
                conn.close()

                self.update_system_status("RUNNING", active_pos_count)

                for ticker in self.tickers:
                    try:
                        self.process_ticker_live_tick(ticker)
                    except Exception as e:
                        print(f"Помилка обробки {ticker}: {e}", flush=True)

                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                self.is_running = False
                self.send_notification("🛑 Демон зупинено оператором.")
                break
            except Exception as e:
                print(f"Помилка циклу демона: {e}", flush=True)
                time.sleep(10)


if __name__ == "__main__":
    daemon = LiveQuantDaemon(poll_interval_seconds=60)
    daemon.run_live_cycle()
