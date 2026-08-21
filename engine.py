"""Scheduled paper-trading engine.

Free-data only. It builds a liquid small-cap candidate proxy from Nasdaq Trader,
uses Yahoo Finance for bars, and SEC EDGAR for filing-risk signals. It never sends
broker orders. GitHub Actions can run this on a schedule and publish data/state.json.
"""
from __future__ import annotations
import io, json, math, os
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import yfinance as yf

ROOT=Path(__file__).parent; DATA=ROOT/'data'; DATA.mkdir(exist_ok=True); STATE=DATA/'state.json'
START=float(os.getenv('STARTING_CASH','1000')); RISK=float(os.getenv('RISK_PER_TRADE','0.005')); MAX_POS=float(os.getenv('MAX_POSITION','0.10')); MAX_DAILY=float(os.getenv('MAX_DAILY_LOSS','0.02')); MAX_OPEN=int(os.getenv('MAX_OPEN_POSITIONS','5')); MIN_SCORE=float(os.getenv('MIN_SCORE','70')); SMALL_CAP_MAX=float(os.getenv('SMALL_CAP_MAX','2000000000'))
SEC_HEADERS={'User-Agent':os.getenv('SEC_USER_AGENT','SmallCapPaperTrader/1.0 contact@example.com'),'Accept-Encoding':'gzip, deflate'}


def load(path,default):
    try:return json.loads(path.read_text())
    except:return default

def save(path,obj):path.write_text(json.dumps(obj,indent=2,default=str))

def indicators(df):
    c=df['Close'].astype(float); h=df['High'].astype(float); l=df['Low'].astype(float); v=df['Volume'].astype(float)
    x=pd.DataFrame({'close':c,'high':h,'low':l,'volume':v}); x['ema9']=c.ewm(span=9,adjust=False).mean(); x['ema20']=c.ewm(span=20,adjust=False).mean(); x['ema50']=c.ewm(span=50,adjust=False).mean()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1); x['atr']=tr.rolling(14).mean(); d=c.diff(); gain=d.clip(lower=0).rolling(14).mean(); loss=(-d.clip(upper=0)).rolling(14).mean(); rs=gain/loss.replace(0,np.nan); x['rsi']=100-(100/(1+rs)); x['vwap']=(c*v).cumsum()/v.cumsum(); x['avgvol20']=v.rolling(20).mean(); x['rvol']=v/x['avgvol20']; x['high20']=h.shift(1).rolling(20).max(); return x

def universe(limit=80):
    url='https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt'; r=requests.get(url,timeout=20); r.raise_for_status(); df=pd.read_csv(io.StringIO(r.text),sep='|',dtype=str); df=df[(df['Test Issue']=='N') & (df['Financial Status']!='D')]; df=df[~df['Symbol'].str.contains(r'\$|\^',na=False)]; return [str(x).replace('/','-') for x in df['NASDAQ Symbol'].head(limit)]

def sec_risk_map(tickers):
    try:
        m=requests.get('https://www.sec.gov/files/company_tickers.json',headers=SEC_HEADERS,timeout=20).json(); cmap={v['ticker'].upper():str(v['cik_str']).zfill(10) for v in m.values()}
    except:return {t:{'risk':0,'items':[]} for t in tickers}
    out={}
    for t in tickers:
        cik=cmap.get(t.upper()); risk=0; items=[]
        if cik:
            try:
                d=requests.get(f'https://data.sec.gov/submissions/CIK{cik}.json',headers=SEC_HEADERS,timeout=15).json()['filings']['recent'];
                for i,form in enumerate(d.get('form',[])[:20]):
                    if form in {'S-1','S-3','S-8','424B2','424B3','424B4','424B5','8-K'}:
                        date=d.get('filingDate',[''])[i]; doc=d.get('primaryDocument',[''])[i]; items.append({'form':form,'date':date,'document':doc})
                        if form in {'S-1','S-3','424B2','424B3','424B4','424B5'}:risk+=25
            except:pass
        out[t]={'risk':min(100,risk),'items':items[:8]}
    return out

def score(t,df,sec):
    x=indicators(df).dropna().iloc[-1]; p=float(x.close); prev=float(df['Close'].iloc[-2]); a=max(float(x.atr),p*.02); change=(p/prev-1)*100; rv=float(x.rvol); rsi=float(x.rsi)
    trend=25 if p>x.ema9>x.ema20>x.ema50 else 13 if p>x.ema20 else 0; vol=min(25,max(0,(rv-1)*10)); breakout=20 if p>=x.high20 else 7; vwap=10 if p>x.vwap else 0; rsi_pts=10 if 52<=rsi<=78 else 5 if 45<=rsi<85 else 0; catalyst=max(0,100-sec['risk'])*.10; score=max(0,min(100,trend+vol+breakout+vwap+rsi_pts+catalyst)); stop=max(.01,p-1.5*a); risk_per_share=p-stop
    return {'ticker':t,'price':round(p,4),'change_pct':round(change,2),'score':round(score,1),'confidence':round(max(0,score-sec['risk']*.3-abs(rsi-65)*.3),1),'rvol':round(rv,2),'rsi':round(rsi,1),'vwap':round(float(x.vwap),4),'atr':round(a,4),'stop':round(stop,4),'target1':round(p+1.5*risk_per_share,4),'target2':round(p+3*risk_per_share,4),'sec_risk':sec['risk'],'sec_items':sec['items'],'data_status':'DELAYED_RESEARCH','small_cap_status':'UNVERIFIED_FREE_DATA','timestamp':datetime.now(timezone.utc).isoformat()}

def run():
    state=load(STATE,{'cash':START,'starting_cash':START,'positions':{},'trades':[],'day_start_equity':START,'enabled':True})
    try:ticks=universe(int(os.getenv('UNIVERSE_SIZE','80')))
    except:ticks=[]
    if not ticks: save(STATE,state); return
    try: daily=yf.download(ticks,period='3mo',interval='1d',auto_adjust=False,progress=False,threads=True,group_by='ticker')
    except Exception as e: state['error']=str(e); save(STATE,state); return
    rough=[]
    for t in ticks:
        try:
            df=daily[t].dropna() if isinstance(daily.columns,pd.MultiIndex) and t in daily.columns.get_level_values(0) else pd.DataFrame()
            if len(df)<55:continue
            p=float(df['Close'].iloc[-1]); av=float(df['Volume'].iloc[-20:].mean()); rv=float(df['Volume'].iloc[-1])/max(av,1)
            if 1<=p<=20 and av>=100000 and (rv>=1.5 or p/float(df['Close'].iloc[-2])-1>=.05):rough.append((t,rv))
        except:continue
    finalists=[t for t,_ in sorted(rough,key=lambda z:z[1],reverse=True)[:20]]; sec=sec_risk_map(finalists); sig=[]
    for t in finalists:
        try:
            df=yf.download(t,period='5d',interval='5m',auto_adjust=False,progress=False,threads=False)
            if isinstance(df.columns,pd.MultiIndex):df.columns=df.columns.get_level_values(0)
            if len(df)>=55:sig.append(score(t,df,sec.get(t,{'risk':0,'items':[]})))
        except:continue
    sig.sort(key=lambda x:x['score'],reverse=True); prices={s['ticker']:s['price'] for s in sig}
    # Manage existing positions first.
    for t,p in list(state['positions'].items()):
        px=prices.get(t,p['entry']); reason=None
        if px<=p['stop']:reason='stop_loss'
        elif px>=p['target1'] and not p.get('partial'):reason='target1'
        elif px>=p['target2']:reason='target2'
        if reason:
            qty=p['qty'] if reason!='target1' else p['qty']*.5; proceeds=qty*px; pnl=(px-p['entry'])*qty; state['cash']+=proceeds; p['qty']-=qty; p['partial']=True; state['trades'].append({'side':'SELL','ticker':t,'qty':round(qty,4),'price':px,'pnl':round(pnl,2),'reason':reason,'time':datetime.now(timezone.utc).isoformat()});
            if p['qty']<=0.0001:del state['positions'][t]
            elif reason=='target1':p['stop']=p['entry']
    equity=state['cash']+sum(p['qty']*prices.get(t,p['entry']) for t,p in state['positions'].items()); daily_loss=max(0,(state['day_start_equity']-equity)/max(state['day_start_equity'],1));
    if daily_loss>=MAX_DAILY:state['enabled']=False
    if state['enabled'] and len(state['positions'])<MAX_OPEN:
        for s in sig:
            if s['score']<MIN_SCORE or s['sec_risk']>=50 or s['ticker'] in state['positions'] or s['stop']>=s['price']:continue
            risk_cash=equity*RISK; qty=min(risk_cash/(s['price']-s['stop']),equity*MAX_POS/s['price'],state['cash']/s['price']); qty=math.floor(max(qty,0)*10000)/10000
            if qty<=0:continue
            cost=qty*s['price']; state['cash']-=cost; state['positions'][s['ticker']]={'qty':qty,'entry':s['price'],'stop':s['stop'],'target1':s['target1'],'target2':s['target2'],'partial':False,'score':s['score'],'opened':datetime.now(timezone.utc).isoformat()}; state['trades'].append({'side':'BUY','ticker':s['ticker'],'qty':qty,'price':s['price'],'score':s['score'],'time':datetime.now(timezone.utc).isoformat()})
            if len(state['positions'])>=MAX_OPEN:break
    state.update({'equity':round(state['cash']+sum(p['qty']*prices.get(t,p['entry']) for t,p in state['positions'].items()),2),'daily_loss_pct':round(daily_loss*100,2),'updated':datetime.now(timezone.utc).isoformat(),'signals':sig[:50],'mode':'PAPER','data_source':'Yahoo Finance + SEC EDGAR + Nasdaq Trader','data_status':'DELAYED_RESEARCH','free_only':True}); save(STATE,state)

if __name__=='__main__':run()
