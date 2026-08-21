"""Free market-data adapters.

Sources:
- Nasdaq Trader symbol directory: public US-listed symbol universe.
- Yahoo Finance via yfinance: historical OHLCV/quote data for research.
- SEC EDGAR: public filings, no API key required.

This module deliberately avoids paid market-data APIs and labels data as delayed/research data.
"""
from __future__ import annotations

import io
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pandas as pd
import yfinance as yf

from .config import settings

NASDAQ_TRADED = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"


class FreeData:
    source = "YAHOO_FINANCE + SEC_EDGAR + NASDAQ_TRADER"

    def __init__(self):
        self.sec_headers = {
            "User-Agent": settings.sec_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        self._sec_map: dict[str, str] | None = None
        self._universe_cache: tuple[float, list[dict[str, Any]]] | None = None

    async def universe(self, refresh=False) -> list[dict[str, Any]]:
        """Return US-listed common stocks from Nasdaq Trader's public symbol file."""
        if self._universe_cache and not refresh and time.time() - self._universe_cache[0] < 86400:
            return self._universe_cache[1]
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(NASDAQ_TRADED)
            r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), sep="|", dtype=str)
        df = df[df["Test Issue"].fillna("N") == "N"]
        df = df[df["Financial Status"].fillna("N") != "D"]
        df = df[~df["Symbol"].str.contains(r"\$|\^", regex=True, na=False)]
        out=[]
        for _, row in df.iterrows():
            symbol=str(row.get("NASDAQ Symbol", row.get("Symbol", ""))).strip()
            if not symbol or symbol == "nan": continue
            out.append({"ticker":symbol.replace("/", "-"), "name":str(row.get("Security Name", "")), "exchange_code":str(row.get("Listing Exchange", ""))})
        self._universe_cache=(time.time(),out)
        return out

    async def bars(self, ticker: str, period="6mo", interval="1d") -> pd.DataFrame:
        """Yahoo historical bars. The returned frame is normalized for our engines."""
        df = await __import__("asyncio").to_thread(
            yf.download, ticker, period=period, interval=interval,
            auto_adjust=False, progress=False, threads=False
        )
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={c:c.lower() for c in df.columns})
        needed=["open","high","low","close","volume"]
        if not all(c in df.columns for c in needed): return pd.DataFrame()
        df=df[needed].dropna(subset=["close"]).copy()
        df.index=pd.to_datetime(df.index, utc=True)
        df["timestamp"]=df.index.astype("int64")//10**6
        return df.reset_index(drop=True)

    async def quote(self, ticker: str) -> dict[str, Any]:
        """Best-effort quote metadata. Yahoo may delay quotes and can throttle requests."""
        def get():
            t=yf.Ticker(ticker)
            fi=getattr(t,"fast_info",{}) or {}
            price=fi.get("last_price") or fi.get("regularMarketPrice")
            prev=fi.get("previous_close") or fi.get("regularMarketPreviousClose")
            return {"ticker":ticker,"price":float(price) if price else None,"previous_close":float(prev) if prev else None,"market_cap":None,"data_status":"DELAYED_RESEARCH"}
        try: return await __import__("asyncio").to_thread(get)
        except Exception: return {"ticker":ticker,"price":None,"previous_close":None,"market_cap":None,"data_status":"UNAVAILABLE"}

    async def sec_ticker_map(self) -> dict[str,str]:
        if self._sec_map is not None: return self._sec_map
        async with httpx.AsyncClient(timeout=20,headers=self.sec_headers) as c:
            r=await c.get(SEC_TICKERS); r.raise_for_status(); data=r.json()
        self._sec_map={v["ticker"].upper():str(v["cik_str"]).zfill(10) for v in data.values()}
        return self._sec_map

    async def filings(self, ticker: str, limit=10) -> list[dict[str,Any]]:
        """Recent SEC submissions with a lightweight catalyst classification."""
        try: cik=(await self.sec_ticker_map()).get(ticker.upper())
        except Exception: return []
        if not cik: return []
        try:
            async with httpx.AsyncClient(timeout=20,headers=self.sec_headers) as c:
                r=await c.get(SEC_SUBMISSIONS.format(cik=cik)); r.raise_for_status(); data=r.json()
            recent=data.get("filings",{}).get("recent",{})
            out=[]
            for i, form in enumerate(recent.get("form",[])[:200]):
                out.append({"form":form,"filing_date":recent.get("filingDate",[""])[i],"accession":recent.get("accessionNumber",[""])[i],"primary_document":recent.get("primaryDocument",[""])[i],"description":recent.get("primaryDocDescription",[""])[i]})
                if len(out)>=limit: break
            return out
        except Exception: return []
