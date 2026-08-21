from __future__ import annotations
import numpy as np
import pandas as pd
from .data import FreeData
from .strategy import score

def indicators(df):
    c=df['Close'].astype(float); h=df['High'].astype(float); l=df['Low'].astype(float); v=df['Volume'].astype(float)
    ema9=c.ewm(span=9,adjust=False).mean().iloc[-1]; ema20=c.ewm(span=20,adjust=False).mean().iloc[-1]; ema50=c.ewm(span=50,adjust=False).mean().iloc[-1]
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1); atr=tr.rolling(14).mean().iloc[-1]
    d=c.diff(); gain=d.clip(lower=0).rolling(14).mean(); loss=(-d.clip(upper=0)).rolling(14).mean(); rs=gain/loss.replace(0,np.nan); rsi=(100-(100/(1+rs))).iloc[-1]
    vwap=(c*v).cumsum().iloc[-1]/max(v.cumsum().iloc[-1],1); rvol=v.iloc[-1]/max(v.rolling(20).mean().iloc[-1],1); high20=h.shift(1).rolling(20).max().iloc[-1]
    return {'price':float(c.iloc[-1]),'change_pct':float((c.iloc[-1]/c.iloc[-2]-1)*100),'ema9':float(ema9),'ema20':float(ema20),'ema50':float(ema50),'atr':float(atr),'rsi':float(rsi),'vwap':float(vwap),'rvol':float(rvol),'prior20_high':float(high20)}

def make_plan(ind, score_value, dilution, account, risk_pct, entry=None):
    entry=float(entry or ind['price']); atr=max(ind['atr'],entry*.02); stop=max(.0001,entry-1.5*atr); risk_share=max(entry-stop,.0001); risk_cash=account*risk_pct/100
    qty=min(risk_cash/risk_share,(account*.10)/entry); qty=max(0,float(np.floor(qty*100)/100)); t1=entry+2*risk_share; t2=entry+3*risk_share
    structure=entry>ind['vwap'] and ind['ema9']>ind['ema20']>=ind['ema50']; rsi_ok=45<=ind['rsi']<=78; volume=ind['rvol']>=1.5; breakout=entry>=ind['prior20_high']; quality=max(0,min(100,score_value-len(dilution)*15))
    if dilution or quality<60: decision='REJECT'
    elif structure and rsi_ok and volume and (breakout or quality>=75): decision='TAKE / PAPER TEST'
    elif quality>=60: decision='WAIT / CONFIRM'
    else: decision='REJECT'
    return {'decision':decision,'quality_score':round(quality,1),'entry':round(entry,4),'stop':round(stop,4),'target1':round(t1,4),'target2':round(t2,4),'risk_cash':round(risk_cash,2),'position_qty':qty,'capital_required':round(qty*entry,2),'risk_per_share':round(risk_share,4),'rr_target1':2.0,'rr_target2':3.0,'checks':{'above_vwap':structure,'rsi_in_range':rsi_ok,'relative_volume':volume,'breakout':breakout,'dilution_flags':dilution}}

async def analyze(ticker, account=1000.0, risk_pct=.5, proposed_entry=None):
    ticker=ticker.strip().upper(); data=FreeData(); bars=await data.bars(ticker,period='3mo',interval='1d')
    if bars is None or len(bars)<55: raise ValueError('Not enough free historical data for this ticker.')
    ind=indicators(bars); filings=await data.filings(ticker,limit=12); text=' '.join(f"{f.get('form','')} {f.get('description','')}" for f in filings); s=score(bars,text); dilution=list(s.get('dilution_flags',[]))
    plan=make_plan(ind,float(s.get('score',0)),dilution,float(account),float(risk_pct),proposed_entry)
    plan.update({'ticker':ticker,'indicators':{k:round(v,4) for k,v in ind.items()},'strategy_score':s.get('score',0),'confidence':s.get('confidence',0),'positive_catalysts':s.get('positive_catalysts',[]),'dilution_flags':dilution,'sec_filings':filings,'data_source':'Yahoo Finance + SEC EDGAR','data_status':'DELAYED_RESEARCH'})
    return plan
