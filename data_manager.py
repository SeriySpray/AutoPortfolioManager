import os
import time
from typing import List, Dict, Optional, Tuple
import pandas as pd
import yfinance as yf
import requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


class DataManager:
    """Robust, cloud-VPS-proof market data downloader and parquet caching manager."""

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_file_path(self, ticker: str) -> str:
        clean = ticker.upper().strip().replace(".", "-")
        return os.path.join(self.cache_dir, f"{clean}.parquet")

    def bootstrap_core_universe(self, tickers: Optional[List[str]] = None) -> int:
        """Preloads and caches historical OHLCV data for the default stock universe."""
        default_list = ["AAPL", "NVDA", "MSFT", "AMZN", "TSLA", "QQQ", "META", "GOOGL"]
        targets = tickers or default_list
        loaded = 0
        for t in targets:
            fp = self._get_file_path(t)
            if not os.path.exists(fp) or os.path.getsize(fp) == 0:
                succ, _, _ = self.download_all_history(t)
                if succ:
                    loaded += 1
            else:
                loaded += 1
        return loaded

    def download_all_history(self, ticker: str) -> Tuple[bool, str, int]:
        """
        Downloads historical Daily OHLCV data with multi-method fallback and cloud IP rate-limit bypass.
        """
        clean_ticker = ticker.upper().strip().replace(".", "-")
        if not clean_ticker:
            return False, "Тікер не може бути порожнім", 0

        df = None
        methods = [
            ("ticker_history_5y", lambda: yf.Ticker(clean_ticker).history(period="5y", auto_adjust=True, timeout=12)),
            ("yf_download_5y", lambda: yf.download(clean_ticker, period="5y", auto_adjust=True, progress=False, timeout=12)),
            ("ticker_history_2y", lambda: yf.Ticker(clean_ticker).history(period="2y", auto_adjust=True, timeout=10)),
            ("yf_download_max", lambda: yf.download(clean_ticker, period="10y", auto_adjust=True, progress=False, timeout=15))
        ]

        for method_name, fetch_fn in methods:
            try:
                df = fetch_fn()
                if df is not None and not df.empty and len(df) >= 30:
                    break
            except Exception:
                time.sleep(0.5)
                continue

        if df is None or df.empty:
            return False, f"Yahoo Finance тимчасово обмежив доступ до '{clean_ticker}'. Спробуйте повторити через кілька секунд.", 0

        try:
            # Handle MultiIndex columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            df = df.reset_index()

            # Normalize Date column
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            elif "Datetime" in df.columns:
                df["Date"] = pd.to_datetime(df["Datetime"]).dt.tz_localize(None)
                df = df.drop(columns=["Datetime"])

            required_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
            for col in required_cols:
                if col not in df.columns:
                    return False, f"Відсутня необхідна колонка: {col}", 0

            df = df[required_cols].sort_values("Date").drop_duplicates(subset=["Date"]).reset_index(drop=True)
            df.dropna(subset=["Close"], inplace=True)

            for c in ["Open", "High", "Low", "Close"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(int)

            df.dropna(subset=["Close"], inplace=True)
            df.reset_index(drop=True, inplace=True)

            file_path = self._get_file_path(clean_ticker)
            df.to_parquet(file_path, index=False, engine="pyarrow")

            rows_count = len(df)
            start_date = df["Date"].min().strftime("%Y-%m-%d")
            end_date = df["Date"].max().strftime("%Y-%m-%d")

            return True, f"Успішно збережено {rows_count} свічок для {clean_ticker} ({start_date} -> {end_date})", rows_count

        except Exception as e:
            return False, f"Помилка обробки даних для {clean_ticker}: {str(e)}", 0

    def get_data_slice(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        auto_download: bool = True
    ) -> Optional[pd.DataFrame]:
        clean_ticker = ticker.upper().strip().replace(".", "-")
        file_path = self._get_file_path(clean_ticker)

        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            if not auto_download:
                return None
            success, _, _ = self.download_all_history(clean_ticker)
            if not success or not os.path.exists(file_path):
                return None

        try:
            df = pd.read_parquet(file_path, engine="pyarrow")
            df["Date"] = pd.to_datetime(df["Date"])

            if start_date:
                start_dt = pd.to_datetime(start_date)
                df = df[df["Date"] >= start_dt]

            if end_date:
                end_dt = pd.to_datetime(end_date)
                df = df[df["Date"] <= end_dt]

            return df.sort_values("Date").reset_index(drop=True)
        except Exception:
            return None

    def list_cached_tickers(self) -> List[Dict[str, str]]:
        if not os.path.exists(self.cache_dir):
            return []

        files = [f for f in os.listdir(self.cache_dir) if f.endswith(".parquet")]
        result = []

        for f in files:
            ticker = f.replace(".parquet", "")
            file_path = os.path.join(self.cache_dir, f)
            try:
                df = pd.read_parquet(file_path, engine="pyarrow")
                if not df.empty and "Date" in df.columns:
                    dates = pd.to_datetime(df["Date"])
                    result.append({
                        "ticker": ticker,
                        "records": len(df),
                        "start_date": dates.min().strftime("%Y-%m-%d"),
                        "end_date": dates.max().strftime("%Y-%m-%d"),
                        "last_price": round(float(df["Close"].iloc[-1]), 2)
                    })
            except Exception:
                continue

        return sorted(result, key=lambda x: x["ticker"])

    def delete_cached_ticker(self, ticker: str) -> bool:
        clean_ticker = ticker.upper().strip().replace(".", "-")
        file_path = self._get_file_path(clean_ticker)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except OSError:
                return False
        return False
