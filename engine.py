import json, os, re, math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
import requests

ROOT=Path(__file__).parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
STATE=DATA/'state.json'
UNIVERSE=DATA/'universe.txt'
STARTING=float(os.getenv('STARTING_CASH','1000'))
RISK=float(os.getenv('RISK_PER_TRADE','0.01'))
MAX_POS=float(os.getenv('MAX_POSITION','0.10'))
MAX_DAILY=float(os.getenv('MAX_DAILY_LOSS','0.03'))

SEC_HEADERS={'User-Agent':os.getenv('SEC_USER_AGENT','PaperTrader research contact@example.com')}


def load_json(path, default):
    try:return json.loads(path.read_text())
    except:return default

def save_json(path,obj): path.write_text(json.dumps(obj,indent=2,default=str))

def indicators(df):
    c=df['Close']; h=df['High']; l=df['Low']; v=df['Volume']
    out=df.copy(); out['ema9']=c.ewm(span=9,adjust=False).mean(); out['ema20']=c.ewm(span=20,adjust=False).mean(); out['ema50']=c.ewm(span=50,adjust=False).mean()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1); out['atr']=tr.rolling(14).mean()
    delta=c.diff(); gain=delta.clip(lower=0).rolling(14).mean(); loss=(-delta.clip(upper=0)).rolling(14).mean(); rs=gain/loss.replace(0,np.nan); out['rsi']=100-(100/(1+rs))
    out['vwap']=(c*v).cumsum()/v.cumsum(); out['avgvol20']=v.rolling(20).mean(); out['rvol']=v/out['avgvol20']; out['high20']=h.shift(1).rolling(20).max(); return out

def sec_signals(ticker):
    url='https://www.sec.gov/files/company_tickers.json'
    # Filing search is intentionally lightweight; SEC facts are used as a free risk source.
    try:
        tickers=requests.get(url,headers=SEC_HEADERS,timeout=10).json()
        cik=next((str(x['cik_str']).zfill(10) for x in tickers.values() if x['ticker'].upper()==ticker.upper()),None)
        if not cik:return {'risk':0,'items':[]}
        submissions=requests.get(f'https://data.sec.gov/submissions/CIK{cik}.json',headers=SEC_HEADERS,timeout=10).json()
        recent=submissions.get('filings',{}).get('recent',{}); items=[]; risk=0
        forms=recent.get('form',[]); dates=recent.get('filingDate',[]); docs=recent.get('primaryDocument',[])
        for form,date,doc in zip(forms[:30],dates[:30],docs[:30]):
            if form in {'S-1','S-3','424B2','424B3','424B4','424B5','8-K'}:
                title=f'{form} filed {date}'; items.append({'form':form,'date':date,'title':title})
                if form.startswith('S-') or form.startswith('424B'): risk+=25
        return {'risk':min(100,risk),'items':items[:8]}
    except Exception as e:return {'risk':0,'items':[],'error':str(e)}

def score(ticker,df,sec):
    x=indicators(df).dropna().iloc[-1]; price=float(x['Close']); atr=float(x['atr'] or price*.05)
    momentum=max(0,min(100,50+(price/float(df['Close'].iloc[-2])-1)*100*2))
    trend=20 if price>x['ema9']>x['ema20']>x['ema50'] else 10 if price>x['ema20'] else 0
    volume=max(0,min(25,float(x['rvol'])*7))
    breakout=20 if price>=x['high20'] else 8
    dilution=max(0,min(30,sec['risk']*.3))
    total=round(max(0,min(100,momentum*.35+trend+volume+breakout-dilution)),1)
    stop=round(price-max(atr*1.5,price*.02),4); target=round(price+max(atr*3,price*.04),4)
    return {'ticker':ticker,'price':round(price,4),'score':total,'rvol':round(float(x['rvol']),2),'rsi':round(float(x['rsi']),1),'vwap':round(float(x['vwap']),4),'ema20':round(float(x['ema20']),4),'atr':round(atr,4),'stop':stop,'target':target,'sec_risk':sec['risk'],'sec_items':sec['items'],'timestamp':datetime.now(timezone.utc).isoformat()}

def run():
    state=load_json(STATE,{'cash':STARTING,'starting_cash':STARTING,'positions':{},'trades':[],'day_start_equity':STARTING,'enabled':True})
    tickers=[x.strip().upper() for x in UNIVERSE.read_text().splitlines() if x.strip() and not x.startswith('#')]
    signals=[]
    for t in tickers:
        try:
            df=yf.download(t,period='3mo',interval='1d',auto_adjust=False,progress=False,threads=False)
            if df.empty:continue
            if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
            signals.append(score(t,df,sec_signals(t)))
        except Exception:continue
    signals.sort(key=lambda x:x['score'],reverse=True)
    prices={x['ticker']:x['price'] for x in signals}
    # Mark existing positions to market and trigger stops/targets.
    for t,p in list(state['positions'].items()):
        price=prices.get(t,p['entry']);
        if price<=p['stop'] or price>=p['target']:
            qty=p['qty']; pnl=(price-p['entry'])*qty; state['cash']+=qty*price; state['trades'].append({'side':'SELL','ticker':t,'qty':qty,'price':price,'pnl':round(pnl,2),'reason':'stop' if price<=p['stop'] else 'target','time':datetime.now(timezone.utc).isoformat()}); del state['positions'][t]
    equity=state['cash']+sum(p['qty']*prices.get(t,p['entry']) for t,p in state['positions'].items())
    daily_loss=max(0,(state['day_start_equity']-equity)/state['day_start_equity'])
    if daily_loss>=MAX_DAILY:state['enabled']=False
    # One new paper position per cycle, only for high-quality signals.
    if state['enabled'] and not state['positions']:
        for s in signals:
            if s['score']<70 or s['sec_risk']>=50 or s['price']<=0 or s['stop']>=s['price']:continue
            risk_cash=equity*RISK; qty=min(risk_cash/(s['price']-s['stop']),equity*MAX_POS/s['price'],state['cash']/s['price']); qty=math.floor(qty*10000)/10000
            if qty>0:
                cost=qty*s['price']; state['cash']-=cost; state['positions'][s['ticker']]={'qty':qty,'entry':s['price'],'stop':s['stop'],'target':s['target'],'opened':datetime.now(timezone.utc).isoformat(),'score':s['score']}; state['trades'].append({'side':'BUY','ticker':s['ticker'],'qty':qty,'price':s['price'],'score':s['score'],'time':datetime.now(timezone.utc).isoformat()}); break
    state['equity']=round(state['cash']+sum(p['qty']*prices.get(t,p['entry']) for t,p in state['positions'].items()),2); state['daily_loss_pct']=round(daily_loss*100,2); state['updated']=datetime.now(timezone.utc).isoformat(); state['signals']=signals[:50]; state['mode']='PAPER'; save_json(STATE,state)

if __name__=='__main__':run()
