"""Free market-data layer for paper trading.
Uses yfinance for research/paper-trading data; no paid API key is required.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Iterable
import pandas as pd
import yfinance as yf

def history(ticker: str, period: str = "5d", interval: str = "5m") -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=False, progress=False, threads=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Open", "High", "Low", "Close"])

def histories(tickers: Iterable[str], period: str = "5d", interval: str = "5m") -> dict[str, pd.DataFrame]:
    return {ticker: history(ticker, period, interval) for ticker in tickers}

def latest(ticker: str) -> dict:
    df = history(ticker, period="1d", interval="5m")
    if df.empty:
        return {"ticker": ticker, "available": False}
    row = df.iloc[-1]
    ts = df.index[-1]
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.tz_localize("UTC")
    return {"ticker": ticker, "available": True, "timestamp": ts.isoformat(), "price": float(row["Close"]), "open": float(row["Open"]), "high": float(row["High"]), "low": float(row["Low"]), "volume": int(row["Volume"]), "source": "Yahoo Finance via yfinance", "retrieved_at": datetime.now(timezone.utc).isoformat()}
