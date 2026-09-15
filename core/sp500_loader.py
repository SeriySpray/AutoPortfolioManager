"""
S&P 500 Data Loader module for AutoPortfolioManager.
Fetches S&P 500 components, downloads historical daily prices with period='max',
and manages local caching via Parquet and JSON files.
"""

import io
import json
import os
import shutil
import time
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
import requests
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
TICKERS_CACHE_FILE = os.path.join(CACHE_DIR, "sp500_tickers.json")
PARQUET_DATA_FILE = os.path.join(CACHE_DIR, "sp500_max_data.parquet")
META_CACHE_FILE = os.path.join(CACHE_DIR, "sp500_meta.json")


def ensure_cache_dir() -> None:
    """Ensure the cache directory exists."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def has_cached_data() -> bool:
    """Check whether local cached historical data exists."""
    return os.path.exists(PARQUET_DATA_FILE) and os.path.getsize(PARQUET_DATA_FILE) > 1024


def clear_cache() -> None:
    """Remove cached parquet and json data files."""
    if os.path.exists(PARQUET_DATA_FILE):
        try:
            os.remove(PARQUET_DATA_FILE)
        except OSError:
            pass
    if os.path.exists(TICKERS_CACHE_FILE):
        try:
            os.remove(TICKERS_CACHE_FILE)
        except OSError:
            pass
    if os.path.exists(META_CACHE_FILE):
        try:
            os.remove(META_CACHE_FILE)
        except OSError:
            pass


def get_sp500_tickers(force_refresh: bool = False) -> Tuple[List[str], Dict[str, Dict[str, str]]]:
    """
    Get the list of S&P 500 tickers and company metadata.
    Uses Wikipedia table with a fallback and local cache.
    Returns: (tickers_list, metadata_dict_by_ticker)
    """
    ensure_cache_dir()
    if not force_refresh and os.path.exists(TICKERS_CACHE_FILE) and os.path.exists(META_CACHE_FILE):
        try:
            with open(TICKERS_CACHE_FILE, "r", encoding="utf-8") as f:
                tickers = json.load(f)
            with open(META_CACHE_FILE, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if tickers and len(tickers) >= 490:
                return tickers, meta
        except Exception:
            pass

    tickers: List[str] = []
    meta: Dict[str, Dict[str, str]] = {}

    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutoPortfolioManager/1.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        tables = pd.read_html(io.StringIO(resp.text))
        df = tables[0]

        for _, row in df.iterrows():
            raw_sym = str(row.get("Symbol", "")).strip().replace(".", "-")
            if not raw_sym or raw_sym == "nan":
                continue
            tickers.append(raw_sym)
            meta[raw_sym] = {
                "name": str(row.get("Security", raw_sym)).strip(),
                "sector": str(row.get("GICS Sector", "Unknown")).strip(),
                "sub_industry": str(row.get("GICS Sub-Industry", "")).strip(),
            }
    except Exception:
        # Resilient fallback list of top S&P 500 components if network fails
        fallback_tickers = [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "BRK-B", "TSLA", "UNH",
            "JNJ", "XOM", "JPM", "V", "PG", "MA", "AVGO", "HD", "CVX", "MRK",
            "ABBV", "COST", "PEP", "KO", "ADBE", "WMT", "BAC", "MCD", "CSCO", "CRM",
            "ACN", "TMO", "LIN", "ABT", "NFLX", "AMD", "DHR", "ORCL", "DIS", "WFC",
            "TXN", "PM", "CAT", "INTC", "VZ", "AMGN", "COP", "IBM", "QCOM", "UNP"
        ]
        tickers = fallback_tickers
        meta = {t: {"name": t, "sector": "S&P 500 Component", "sub_industry": ""} for t in fallback_tickers}

    # Save to cache
    with open(TICKERS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(tickers, f, indent=2)
    with open(META_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return tickers, meta


def download_sp500_max_data(
    tickers: List[str],
    batch_size: int = 50,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> pd.DataFrame:
    """
    Download maximum historical daily data for all tickers in batches.
    Extracts 'Close' prices and aggregates into a single DataFrame.
    """
    ensure_cache_dir()
    all_series: Dict[str, pd.Series] = {}
    total_tickers = len(tickers)

    for i in range(0, total_tickers, batch_size):
        chunk = tickers[i : i + batch_size]
        chunk_str = " ".join(chunk)
        if progress_callback:
            progress_callback(min(i + batch_size, total_tickers), total_tickers, f"Downloading chunk {i // batch_size + 1} ({len(chunk)} tickers)...")

        try:
            # auto_adjust=True guarantees dividend and split adjustments
            data = yf.download(
                chunk_str,
                period="max",
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=True,
            )

            if data.empty:
                continue

            # Handle multi-level columns if multiple tickers returned
            if isinstance(data.columns, pd.MultiIndex):
                # Standard yfinance format: level 0 is Price (Close, Open, etc.), level 1 is Ticker
                # or level 0 is Ticker, level 1 is Price
                if "Close" in data.columns.levels[0]:
                    close_df = data["Close"]
                    for sym in chunk:
                        if sym in close_df.columns:
                            s = close_df[sym].dropna()
                            if not s.empty:
                                all_series[sym] = s
                elif "Close" in data.columns.levels[1]:
                    for sym in chunk:
                        try:
                            s = data.xs(key=("Close", sym), level=(0, 1), axis=1).dropna()
                            if not s.empty:
                                all_series[sym] = s
                        except KeyError:
                            pass
            else:
                # Single ticker returned in chunk
                if "Close" in data.columns and len(chunk) == 1:
                    s = data["Close"].dropna()
                    if not s.empty:
                        all_series[chunk[0]] = s

        except Exception as e:
            # Soft fallback: proceed with next chunk without aborting
            pass

        # Small courtesy delay between chunks to avoid aggressive rate limiting
        time.sleep(0.3)

    if not all_series:
        raise RuntimeError("No historical data could be retrieved for S&P 500 tickers.")

    # Combine into a single daily DataFrame
    combined_df = pd.DataFrame(all_series)
    combined_df.index = pd.to_datetime(combined_df.index)
    combined_df = combined_df.sort_index()

    # Save to Parquet cache
    combined_df.to_parquet(PARQUET_DATA_FILE, engine="pyarrow", compression="snappy")

    return combined_df


def load_sp500_data(
    force_refresh: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, str]]]:
    """
    High-level loader: Returns cached DataFrame if available, otherwise downloads and caches.
    Returns: (prices_dataframe, metadata_dict)
    """
    tickers, meta = get_sp500_tickers(force_refresh=force_refresh)

    if not force_refresh and has_cached_data():
        try:
            df = pd.read_parquet(PARQUET_DATA_FILE, engine="pyarrow")
            return df, meta
        except Exception:
            # Corrupted cache fallback
            pass

    df = download_sp500_max_data(tickers, batch_size=60, progress_callback=progress_callback)
    return df, meta
