"""Market data access. Paper-trading prototype: EOD data from Yahoo Finance via yfinance.
Cached locally; deterministic synthetic series used only if network and cache both fail."""
import os, hashlib
import numpy as np
import pandas as pd

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data_cache")
SYMBOLS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]
INDEX = "^NSEI"

def _cache_path(symbol):
    return os.path.join(CACHE, symbol.replace("^", "IDX") + ".csv")

def synthetic_history(symbol, days=260):
    seed = int(hashlib.md5(symbol.encode()).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    rets = rng.normal(0.0004, 0.014, days)
    close = 1000 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"Open": close * (1 + rng.normal(0, 0.003, days)),
                       "High": close * (1 + abs(rng.normal(0, 0.006, days))),
                       "Low": close * (1 - abs(rng.normal(0, 0.006, days))),
                       "Close": close, "Volume": rng.integers(1e6, 5e6, days)}, index=dates)
    df.attrs["source"] = "SYNTHETIC (offline fallback)"
    return df

def load_history(symbol, period="1y"):
    os.makedirs(CACHE, exist_ok=True)
    try:
        import yfinance as yf
        df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df is not None and len(df) > 60:
            df.to_csv(_cache_path(symbol))
            df.attrs["source"] = "Yahoo Finance EOD (yfinance)"
            return df
    except Exception:
        pass
    if os.path.exists(_cache_path(symbol)):
        df = pd.read_csv(_cache_path(symbol), index_col=0, parse_dates=True)
        df.attrs["source"] = "Yahoo Finance EOD (local cache)"
        return df
    return synthetic_history(symbol)
