import re
from .indicators import add_features

BAD=['offering','registered direct','atm offering','convertible','warrant','dilution','dilutive','reverse split','going concern','bankruptcy']
GOOD=['fda','approval','contract','award','acquisition','partnership','agreement','government','order','guidance','earnings','revenue']

def catalyst_score(text):
    t=(text or '').lower(); bad=sum(x in t for x in BAD); good=sum(x in t for x in GOOD); return max(0,min(100,50+good*9-bad*18)), bad, good

def score(df,catalyst=''):
    if len(df)<55: return None
    x=add_features(df).iloc[-1]
    cs,bad,good=catalyst_score(catalyst)
    vals={'trend':0,'volume':0,'breakout':0,'vwap':0,'rsi':0,'catalyst':cs,'risk_penalty':bad*12}
    vals['trend']=25 if x.ema9>x.ema20>x.ema50 else 10 if x.ema9>x.ema20 else 0
    vals['volume']=min(25,max(0,(float(x.rvol)-1)*8))
    vals['breakout']=20 if x.close>=x.high20*.995 else 8 if x.close>x.ema20 else 0
    vals['vwap']=15 if x.close>x.vwap else 0
    vals['rsi']=10 if 52<=x.rsi<=78 else 4 if 45<=x.rsi<85 else 0
    raw=sum(vals.values())-vals['risk_penalty']; total=max(0,min(100,raw))
    confidence=max(0,min(100,total-abs(float(x.rsi)-65)*.25))
    return {'score':round(total,1),'confidence':round(confidence,1),'features':{k:round(float(v),2) for k,v in vals.items()},'price':float(x.close),'atr':float(x.atr) if x.atr==x.atr else 0,'rvol':float(x.rvol) if x.rvol==x.rvol else 0,'rsi':float(x.rsi) if x.rsi==x.rsi else 0,'catalyst_score':cs,'dilution_flags':bad}

def levels(signal):
    p=signal['price']; a=signal['atr'] or p*.05; stop=max(0.01,p-1.5*a); risk=p-stop; return {'entry':p,'stop':round(stop,4),'target1':round(p+1.5*risk,4),'target2':round(p+3*risk,4)}
