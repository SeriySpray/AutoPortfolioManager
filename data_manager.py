import os
from typing import List, Dict, Optional, Tuple
import pandas as pd
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


class DataManager:
    """Manages downloading, local caching in Parquet, and date slicing for stock market data."""

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_file_path(self, ticker: str) -> str:
        # Standardize ticker: replace . with - (e.g., BRK.B -> BRK-B)
        clean = ticker.upper().strip().replace(".", "-")
        return os.path.join(self.cache_dir, f"{clean}.parquet")

    def download_all_history(self, ticker: str) -> Tuple[bool, str, int]:
        """
        Downloads the complete historical Daily OHLCV data for a ticker using yfinance
        with auto_adjust=True (split and dividend adjusted) to prevent split-induced data corruption.
        """
        clean_ticker = ticker.upper().strip().replace(".", "-")
        if not clean_ticker:
            return False, "Тікер не може бути порожнім", 0

        try:
            stock = yf.Ticker(clean_ticker)
            # auto_adjust=True ensures Open, High, Low, Close are split-adjusted
            df = stock.history(period="max", auto_adjust=True)

            if df.empty:
                return False, f"Дані для тікера '{clean_ticker}' не знайдено або вони недоступні.", 0

            df = df.reset_index()
            # Normalize Date column to timezone-naive datetime64[ns]
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

            # Ensure numeric types
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
            return False, f"Помилка завантаження даних для {clean_ticker}: {str(e)}", 0

    def get_data_slice(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        Retrieves a slice of historical data for a ticker between start_date and end_date.
        If not yet downloaded, downloads it automatically.
        """
        clean_ticker = ticker.upper().strip().replace(".", "-")
        file_path = self._get_file_path(clean_ticker)

        if not os.path.exists(file_path):
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
                # Include end date up to end of that day
                end_dt = pd.to_datetime(end_date)
                df = df[df["Date"] <= end_dt]

            return df.sort_values("Date").reset_index(drop=True)
        except Exception as e:
            print(f"Error reading cache for {clean_ticker}: {e}")
            return None

    def list_cached_tickers(self) -> List[Dict]:
        """Lists all locally cached tickers with their date ranges and record counts."""
        result = []
        if not os.path.exists(self.cache_dir):
            return result

        for fname in os.listdir(self.cache_dir):
            if fname.endswith(".parquet"):
                ticker = fname[:-8]
                file_path = os.path.join(self.cache_dir, fname)
                try:
                    df = pd.read_parquet(file_path, columns=["Date", "Close"], engine="pyarrow")
                    if not df.empty:
                        df["Date"] = pd.to_datetime(df["Date"])
                        start_date = df["Date"].min().strftime("%Y-%m-%d")
                        end_date = df["Date"].max().strftime("%Y-%m-%d")
                        count = len(df)
                        last_close = float(df["Close"].iloc[-1])
                        result.append({
                            "ticker": ticker,
                            "records": count,
                            "start_date": start_date,
                            "end_date": end_date,
                            "last_price": round(last_close, 2),
                            "file_size_kb": round(os.path.getsize(file_path) / 1024, 1)
                        })
                except Exception as e:
                    print(f"Error inspecting {fname}: {e}")

        result.sort(key=lambda x: x["ticker"])
        return result

    def delete_cached_ticker(self, ticker: str) -> bool:
        """Removes a ticker from the local cache."""
        clean_ticker = ticker.upper().strip().replace(".", "-")
        file_path = self._get_file_path(clean_ticker)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
