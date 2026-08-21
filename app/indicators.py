import numpy as np
import pandas as pd

def atr(df,n=14):
    h,l,c=df.high,df.low,df.close; tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1); return tr.rolling(n).mean()

def rsi(s,n=14):
    d=s.diff(); up=d.clip(lower=0).rolling(n).mean(); down=(-d.clip(upper=0)).rolling(n).mean(); rs=up/down.replace(0,np.nan); return 100-(100/(1+rs))

def add_features(df):
    x=df.copy(); x['ema9']=x.close.ewm(span=9,adjust=False).mean(); x['ema20']=x.close.ewm(span=20,adjust=False).mean(); x['ema50']=x.close.ewm(span=50,adjust=False).mean(); x['vwap']=(x.close*x.volume).cumsum()/x.volume.cumsum(); x['atr']=atr(x); x['rsi']=rsi(x.close); x['vol20']=x.volume.rolling(20).mean(); x['rvol']=x.volume/x.vol20; x['high20']=x.high.rolling(20).max(); x['low20']=x.low.rolling(20).min(); x['range_pct']=(x.high-x.low)/x.close; return x
