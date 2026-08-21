import httpx
import pandas as pd
from datetime import date,timedelta
from .config import settings

BASE='https://api.massive.com'
class Massive:
    def __init__(self): self.key=settings.massive_key
    async def get(self,path,params=None):
        if not self.key: return None
        p=dict(params or {}); p['apiKey']=self.key
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.get(BASE+path,params=p); r.raise_for_status(); return r.json()
    async def tickers(self): return await self.get('/v3/reference/tickers',{'market':'stocks','locale':'us','active':'true','limit':1000})
    async def daily(self,ticker,days=90):
        end=date.today(); start=end-timedelta(days=days)
        d=await self.get(f'/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}',{'adjusted':'true','sort':'asc','limit':5000}) or {}
        rows=d.get('results',[]); return pd.DataFrame([{'timestamp':r.get('t'),'open':r.get('o'),'high':r.get('h'),'low':r.get('l'),'close':r.get('c'),'volume':r.get('v')} for r in rows])
    async def minute(self,ticker,minutes=120):
        end=date.today(); start=end-timedelta(days=2)
        d=await self.get(f'/v2/aggs/ticker/{ticker}/range/1/minute/{start}/{end}',{'adjusted':'true','sort':'asc','limit':50000}) or {}
        rows=d.get('results',[]); return pd.DataFrame([{'timestamp':r.get('t'),'open':r.get('o'),'high':r.get('h'),'low':r.get('l'),'close':r.get('c'),'volume':r.get('v')} for r in rows[-minutes:]])
